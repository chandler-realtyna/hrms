from __future__ import annotations

import base64
import hashlib
import json

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, now_datetime

from hrms.api.weekly_timesheet import _is_hr, _hr_employee_image, _week_bounds
from hrms.api.project_review_followup import _reminder_recipient, _reminder_subject
from hrms.utils.review_query_permissions import hr_read_condition


class TeamCursorResetRequired(frappe.ValidationError):
	pass


def _cursor_context(view, filters):
	effective = {key: filters[key] for key in ("employee", "project", "company", "status", "search", "from_date", "to_date", "review_scope", "week_start") if filters.get(key)}
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
	if filters.get("review_scope") not in {None, "", "all", "submitted", "draft"}:
		frappe.throw(_("Unknown project follow-up scope."))
	if filters.get("week_start"):
		filters["week_start"] = str(_week_bounds(filters["week_start"])[0])
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
	hr = _is_hr()
	if not hr and not employee:
		return dict(rows=[], total=0, next_cursor=None)
	args = dict(employee=employee or "", final="Closed")
	where = ["t.custom_is_weekly = 1", "t.docstatus < 2", "t.employee != %(employee)s", "d.project IS NOT NULL", "d.from_time IS NOT NULL"]
	active_employee = "(e.status = 'Active' AND e.docstatus < 2 AND COALESCE(u.enabled, 0) = 1)"
	where.append(f"(t.custom_weekly_status = %(final)s OR NOT COALESCE({active_employee}, 0) OR a.status IN ('Approved', 'HR Review'))" if view == "history" else f"COALESCE(t.custom_weekly_status, 'Draft') != %(final)s AND {active_employee} AND COALESCE(a.status, 'Draft') NOT IN ('Approved', 'HR Review')")
	if not hr:
		where.append("(p.custom_project_lead = %(employee)s OR p.custom_project_manager = %(employee)s)")
	if hr:
		for doctype, alias in (("Timesheet", "t"), ("Project", "p")):
			condition = hr_read_condition(doctype, alias)
			if condition:
				where.append(condition)
	for field in ("employee", "project"):
		if filters.get(field):
			args["filter_"+field] = filters[field]
			where.append(f"{'t' if field == 'employee' else 'd'}.{field} = %(filter_{field})s")
	if filters.get("review_scope") == "submitted":
		where.append("t.custom_weekly_submitted_at IS NOT NULL")
	elif filters.get("review_scope") == "draft":
		where.append("t.custom_weekly_submitted_at IS NULL")
	if filters.get("week_start"):
		args["week_start"] = filters["week_start"]
		where.append("t.custom_week_start = %(week_start)s")
	if filters.get("company"):
		args["company"] = filters["company"]
		where.append("t.company = %(company)s")
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
		LEFT JOIN tabEmployee e ON e.name=t.employee
		LEFT JOIN tabUser u ON u.name=e.user_id
		LEFT JOIN `tabTimesheet Project Approval` a ON a.parent=t.name AND a.project=d.project
		WHERE """ + " AND ".join(where)
	group = " GROUP BY t.name, d.project"
	# Scope and filters are identical for count and page; no pre-scope row cap.
	total = frappe.db.sql("SELECT COUNT(*) FROM (SELECT t.name " + base + group + ") scoped", args)[0][0]
	section_query = """SELECT t.name AS timesheet, t.employee, t.employee_name,
		t.custom_week_start AS week_start, t.custom_week_end AS week_end,
		t.custom_weekly_status AS hr_status, t.company, t.modified, t.docstatus, e.user_id AS owner_user,
		NOT COALESCE((e.status = 'Active' AND e.docstatus < 2 AND COALESCE(u.enabled, 0) = 1), 0) AS inactive_employee,
		t.custom_weekly_submitted_at AS submitted_at, d.project,
		p.project_name AS project_label, p.custom_project_lead AS project_lead, p.custom_project_manager AS project_manager,
		a.name AS approval_name, COALESCE(a.status, 'Draft') AS project_status,
		a.return_reason, a.reviewed_by, a.reviewed_at,
		SUM(d.hours) AS hours, COUNT(d.name) AS log_count
		""" + base + group
	actionable = "docstatus=0 AND hr_status IN ('Draft', 'Pending Project Approval', 'Correction Required') AND project_status IN ('Draft', 'Pending')"
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
	images, reviewers = {}, {}
	for row in rows:
		if row.employee not in images:
			images[row.employee] = _hr_employee_image(row.employee)
		row.employee_image = images[row.employee]
		lead = row.project_lead
		if lead and lead not in reviewers:
			reviewers[lead] = frappe.db.get_value("Employee", lead, "employee_name")
		row.reviewer_name = reviewers.get(lead)
		row.activity_types = sorted(set(frappe.db.get_all("Timesheet Detail", filters={"parent": row.timesheet, "project": row.project}, pluck="activity_type")) - {None, ""})
		row.is_own_section = False
		row.waiting_since = str(row.reviewed_at or row.modified) if row.project_status == "Returned" else str(row.submitted_at or row.modified) if row.project_status in {"Draft", "Pending"} else None
		row.waiting_days = max(0, (now_datetime() - get_datetime(row.waiting_since)).days) if row.waiting_since else None
		row.can_ping = bool(hr and row.owner_user != frappe.session.user and not row.inactive_employee and row.docstatus == 0 and row.hr_status == "Pending Project Approval" and row.submitted_at and row.project_status == "Pending" and row.project_lead != row.employee)
		if row.can_ping:
			recipient = _reminder_recipient(row.project, row.owner_user)
			row.can_ping = bool(recipient and recipient != frappe.session.user and frappe.has_permission("Timesheet", "read", doc=row.timesheet))
			row.ping_reviewer = recipient if row.can_ping else None
			row.ping_reviewer_name = frappe.db.get_value("User", recipient, "full_name") if recipient else None
			row.last_ping_at = str(frappe.db.get_value("Notification Log", {"document_type": "Timesheet", "document_name": row.timesheet, "for_user": recipient, "subject": _reminder_subject(row.project)}, "creation", order_by="creation desc") or "") if recipient else ""
		row.regular_reviewer = bool(employee and employee in {row.project_lead, row.project_manager})
		row.actionable = view == "current" and row.docstatus == 0 and row.hr_status in {"Draft", "Pending Project Approval", "Correction Required"} and row.project_status in {"Draft", "Pending"}
		row.selection_reason = "Approve saved entries now; changes will require another review." if row.actionable else {
			"Draft": "Employee must submit the week first.",
			"Returned": "Waiting for correction and resubmission.",
			"Approved": "Project already approved; the week is not final until HR closes it.",
			"HR Review": "This section is routed to HR, not project approval.",
		}.get(row.project_status, "This week is not ready for project approval.")
		if view == "history":
			row.selection_reason = ("Employee account is inactive. This record is archived for HR follow-up." if row.inactive_employee
				else "This week is final and read-only." if row.hr_status == "Closed"
				else "Project review is complete. Final weekly approval is handled separately by HR.")
		row.routed_to_hr_reason = ("self" if row.project_lead == row.employee else "no_lead" if not row.project_lead else None) if row.project_status == "HR Review" else None
		for field in ("modified", "week_start", "week_end", "submitted_at", "reviewed_at"):
			row[field] = str(row[field]) if row[field] else None
		row.pop("project_lead", None)
		for field, _direction in ordering:
			if field.startswith("_"):
				row.pop(field, None)
	return dict(rows=rows, total=total, next_cursor=next_cursor, can_hr_followup=hr)
