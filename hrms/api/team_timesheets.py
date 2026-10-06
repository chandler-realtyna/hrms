from __future__ import annotations

import base64
import hashlib
import json

import frappe
from frappe import _
from frappe.utils import getdate

from hrms.api.weekly_timesheet import _is_hr


class TeamCursorResetRequired(frappe.ValidationError):
	pass


def _cursor_context(view, filters):
	effective = {key: filters[key] for key in ("employee", "project", "status", "search", "from_date", "to_date") if filters.get(key)}
	return hashlib.sha256(json.dumps([frappe.session.user, view, effective], sort_keys=True).encode()).hexdigest()


def _page_condition(cursor, view, context, ordering, args):
	if not cursor:
		return ""
	try:
		decoded = json.loads(base64.urlsafe_b64decode(str(cursor)).decode())
		if (not isinstance(decoded, dict) or decoded.get("v") != 2
			or decoded.get("view") != view or decoded.get("context") != context):
			raise ValueError()
		keys = decoded["keys"]
		if not isinstance(keys, list) or len(keys) != len(ordering) or any(not isinstance(v, str) for v in keys):
			raise ValueError()
	except (ValueError, TypeError, UnicodeError, KeyError):
		frappe.throw(_("This list order changed. Reload from the first page."), TeamCursorResetRequired)
	# Mixed ascending and descending keys need a lexicographic keyset predicate.
	terms, equal = [], []
	for index, (field, direction) in enumerate(ordering):
		key = f"page_{index}"
		args[key] = keys[index]
		operator = ">" if direction == "ASC" else "<"
		terms.append("(" + " AND ".join(equal + [f"{field} {operator} %({key})s"]) + ")")
		equal.append(f"{field} = %({key})s")
	return " WHERE " + " OR ".join(terms)


def get_sections(view="current", cursor=None, filters=None):
	if view not in {"current", "history"}:
		frappe.throw(_("Unknown timesheet view."))
	filters = frappe.parse_json(filters) or {}
	if not isinstance(filters, dict):
		frappe.throw(_("Invalid timesheet filters."))
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
	hr = _is_hr()
	if not hr and not employee:
		return dict(rows=[], total=0, next_cursor=None)
	args = dict(employee=employee or "", final="Closed")
	where = ["t.custom_is_weekly = 1", "t.docstatus < 2", "t.employee != %(employee)s", "d.project IS NOT NULL", "d.from_time IS NOT NULL"]
	where.append("t.custom_weekly_status = %(final)s" if view == "history" else "COALESCE(t.custom_weekly_status, 'Draft') != %(final)s")
	if not hr:
		where.append("(p.custom_project_lead = %(employee)s OR p.custom_project_manager = %(employee)s)")
	for field in ("employee", "project"):
		if filters.get(field):
			args["filter_"+field] = filters[field]
			where.append(f"{'t' if field == 'employee' else 'd'}.{field} = %(filter_{field})s")
	if filters.get("status"):
		args["status"] = filters["status"]
		where.append("COALESCE(a.status, 'Draft') = %(status)s")
	if filters.get("search"):
		args["search"] = "%" + str(filters["search"])[:200] + "%"
		where.append("(t.employee_name LIKE %(search)s OR p.project_name LIKE %(search)s OR d.project LIKE %(search)s OR EXISTS (SELECT 1 FROM `tabTimesheet Detail` activity WHERE activity.parent=t.name AND activity.project=d.project AND activity.activity_type LIKE %(search)s))")
	for key, operator in (("from_date", ">="), ("to_date", "<=")):
		if filters.get(key):
			args[key] = getdate(filters[key])
			where.append(f"t.custom_week_start {operator} %({key})s")
	base = """
		FROM tabTimesheet t
		JOIN `tabTimesheet Detail` d ON d.parent=t.name AND d.parenttype='Timesheet'
		JOIN tabProject p ON p.name=d.project
		LEFT JOIN `tabTimesheet Project Approval` a ON a.parent=t.name AND a.project=d.project
		WHERE """ + " AND ".join(where)
	group = " GROUP BY t.name, d.project"
	# Scope and filters are identical for count and page; no pre-scope row cap.
	total = frappe.db.sql("SELECT COUNT(*) FROM (SELECT t.name " + base + group + ") scoped", args)[0][0]
	section_query = """SELECT t.name AS timesheet, t.employee, t.employee_name,
		t.custom_week_start AS week_start, t.custom_week_end AS week_end,
		t.custom_weekly_status AS hr_status, t.modified, t.docstatus,
		t.custom_weekly_submitted_at AS submitted_at, d.project,
		p.project_name AS project_label, p.custom_project_lead AS project_lead,
		a.name AS approval_name, COALESCE(a.status, 'Draft') AS project_status,
		a.return_reason, a.reviewed_by, a.reviewed_at,
		SUM(d.hours) AS hours, COUNT(d.name) AS log_count
		""" + base + group
	actionable = "docstatus=0 AND submitted_at IS NOT NULL AND hr_status IN ('Pending Project Approval', 'Correction Required') AND project_status='Pending'"
	if view == "current":
		sort_fields = f"""
			CASE WHEN {actionable} THEN 0 WHEN project_status='Draft' THEN 1
				WHEN project_status='Returned' THEN 2 WHEN project_status='Approved' THEN 4 ELSE 3 END AS _priority,
			CASE WHEN {actionable} THEN COALESCE(week_start, '9999-12-31') ELSE '1000-01-01' END AS _sort_week,
			CASE WHEN {actionable} THEN COALESCE(submitted_at, modified) ELSE '1000-01-01 00:00:00' END AS _sort_submitted,
			CASE WHEN {actionable} THEN '1000-01-01 00:00:00' ELSE modified END AS _sort_modified
		"""
		ordering = [("_priority", "ASC"), ("_sort_week", "ASC"), ("_sort_submitted", "ASC"), ("_sort_modified", "DESC")]
	else:
		sort_fields = "COALESCE(week_start, '1000-01-01') AS _sort_week, modified AS _sort_modified"
		ordering = [("_sort_week", "DESC"), ("_sort_modified", "DESC")]
	ordering += [("timesheet", "DESC"), ("project", "DESC")]
	context = _cursor_context(view, filters)
	condition = _page_condition(cursor, view, context, ordering, args)
	query = f"SELECT * FROM (SELECT sections.*, {sort_fields} FROM ({section_query}) sections) ranked"
	query += condition + " ORDER BY " + ", ".join(f"{field} {direction}" for field, direction in ordering) + " LIMIT 51"
	rows = frappe.db.sql(query, args, as_dict=True)
	has_more = len(rows) > 50
	rows = rows[:50]
	next_cursor = None
	if has_more:
		next_cursor = base64.urlsafe_b64encode(json.dumps(dict(v=2, view=view, context=context,
			keys=[str(rows[-1][field]) for field, _direction in ordering])).encode()).decode()
	for row in rows:
		row.activity_types = sorted(set(frappe.db.get_all("Timesheet Detail", filters={"parent": row.timesheet, "project": row.project}, pluck="activity_type")) - {None, ""})
		row.is_own_section = False
		row.actionable = view == "current" and row.docstatus == 0 and bool(row.submitted_at) and row.hr_status in {"Pending Project Approval", "Correction Required"} and row.project_status == "Pending"
		row.selection_reason = "Select for approval" if row.actionable else {
			"Draft": "Employee must submit the week first.",
			"Returned": "Waiting for correction and resubmission.",
			"Approved": "Project already approved; the week is not final until HR closes it.",
			"HR Review": "This section is routed to HR, not project approval.",
		}.get(row.project_status, "This week is not ready for project approval.")
		if view == "history":
			row.selection_reason = "This week is final and read-only."
		row.routed_to_hr_reason = ("self" if row.project_lead == row.employee else "no_lead" if not row.project_lead else None) if row.project_status == "HR Review" else None
		for field in ("modified", "week_start", "week_end", "submitted_at", "reviewed_at"):
			row[field] = str(row[field]) if row[field] else None
		row.pop("project_lead", None)
		for field, _direction in ordering:
			if field.startswith("_"):
				row.pop(field, None)
	return dict(rows=rows, total=total, next_cursor=next_cursor)
