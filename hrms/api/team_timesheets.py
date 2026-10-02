from __future__ import annotations

import base64
import json

import frappe
from frappe import _
from frappe.utils import getdate

from hrms.api.weekly_timesheet import _is_hr


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
	if cursor:
		try:
			decoded = json.loads(base64.urlsafe_b64decode(str(cursor)).decode())
			if not isinstance(decoded, list) or len(decoded) != 3 or any(not isinstance(v, str) for v in decoded):
				raise ValueError()
		except (ValueError, TypeError, UnicodeError):
			frappe.throw(_("Invalid page cursor."))
		args.update(modified=decoded[0], name=decoded[1], project=decoded[2])
		base += " AND (t.modified, t.name, d.project) < (%(modified)s, %(name)s, %(project)s)"
	rows = frappe.db.sql("""SELECT t.name AS timesheet, t.employee, t.employee_name,
		t.custom_week_start AS week_start, t.custom_week_end AS week_end,
		t.custom_weekly_status AS hr_status, t.modified, t.docstatus,
		t.custom_weekly_submitted_at AS submitted_at, d.project,
		p.project_name AS project_label, p.custom_project_lead AS project_lead,
		a.name AS approval_name, COALESCE(a.status, 'Draft') AS project_status,
		a.return_reason, a.reviewed_by, a.reviewed_at,
		SUM(d.hours) AS hours, COUNT(d.name) AS log_count
		""" + base + group + " ORDER BY t.modified DESC, t.name DESC, d.project DESC LIMIT 51", args, as_dict=True)
	has_more = len(rows) > 50
	rows = rows[:50]
	for row in rows:
		row.activity_types = sorted(set(frappe.db.get_all("Timesheet Detail", filters={"parent": row.timesheet, "project": row.project}, pluck="activity_type")) - {None, ""})
		row.is_own_section = False
		row.actionable = view == "current" and row.docstatus == 0 and row.hr_status == "Pending Project Approval" and row.project_status == "Pending"
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
	next_cursor = base64.urlsafe_b64encode(json.dumps([rows[-1].modified, rows[-1].timesheet, rows[-1].project]).encode()).decode() if has_more else None
	return dict(rows=rows, total=total, next_cursor=next_cursor)
