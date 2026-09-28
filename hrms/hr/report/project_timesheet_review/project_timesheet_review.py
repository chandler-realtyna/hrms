# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Project Timesheet Review (Desk).

Project-scoped review of submitted weekly timesheets. Data-level scoping is
enforced here (never trust client filters alone):
  - HR roles see every project section.
  - Project Leads see only projects where they are the active lead.
  - Everyone else sees an empty table.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Timesheet"), "fieldname": "timesheet", "fieldtype": "Link", "options": "Timesheet", "width": 150},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 130},
		{"label": _("Project Lead"), "fieldname": "project_lead", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Week Start"), "fieldname": "week_start", "fieldtype": "Date", "width": 100},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Hours"), "fieldname": "hours", "fieldtype": "Float", "width": 80},
		{"label": _("Logs"), "fieldname": "log_count", "fieldtype": "Int", "width": 60},
		{"label": _("Project Status"), "fieldname": "project_status", "fieldtype": "Data", "width": 130},
		{"label": _("HR Status"), "fieldname": "hr_status", "fieldtype": "Data", "width": 150},
		{"label": _("Submitted"), "fieldname": "submitted_at", "fieldtype": "Datetime", "width": 160},
		{"label": _("Modified"), "fieldname": "modified", "fieldtype": "Datetime", "width": 160},
	]


def _lead_projects():
	"""Open projects led by the session user's employee (empty set if none)."""
	employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
	)
	if not employee:
		return set()
	rows = frappe.db.get_all(
		"Project", filters={"custom_project_lead": employee, "status": "Open"}, pluck="name"
	)
	return set(rows)


def _is_hr():
	return bool({"HR Manager", "HR User"}.intersection(frappe.get_roles()))


def get_data(filters):
	filters = frappe._dict(filters or {})
	hr = _is_hr()
	lead_projects = _lead_projects()
	if not hr and not lead_projects:
		return []

	conditions = ["a.status IN ('Pending', 'Approved', 'Returned', 'HR Review')"]
	values = {}
	if filters.get("project"):
		conditions.append("a.project = %(project)s")
		values["project"] = filters.project
	if filters.get("project_status"):
		conditions.append("a.status = %(project_status)s")
		values["project_status"] = filters.project_status
	if filters.get("employee"):
		conditions.append("t.employee = %(employee)s")
		values["employee"] = filters.employee
	if filters.get("week_start"):
		conditions.append("t.custom_week_start = %(week_start)s")
		values["week_start"] = filters.week_start
	if filters.get("hr_status"):
		conditions.append("t.custom_weekly_status = %(hr_status)s")
		values["hr_status"] = filters.hr_status
	if filters.get("project_lead"):
		conditions.append(
			"""EXISTS (SELECT 1 FROM `tabProject` p
				WHERE p.name = a.project AND p.custom_project_lead = %(project_lead)s)"""
		)
		values["project_lead"] = filters.project_lead

	rows = frappe.db.sql(
		f"""SELECT a.name AS approval_name, a.parent AS timesheet, a.project,
			a.status AS project_status, a.controller,
			t.employee, t.title AS employee_name,
			t.custom_week_start AS week_start, t.custom_week_end AS week_end,
			t.custom_weekly_status AS hr_status,
			t.custom_weekly_submitted_at AS submitted_at, t.modified AS modified
		FROM `tabTimesheet Project Approval` a
		INNER JOIN `tabTimesheet` t ON t.name = a.parent
		WHERE t.docstatus = 0 AND t.custom_weekly_submitted_at IS NOT NULL
			AND {' AND '.join(conditions)}
		ORDER BY t.custom_week_start DESC, a.project, t.employee""",
		values,
		as_dict=True,
	)

	project_names = list({r.project for r in rows})
	lead_map = {}
	label_map = {}
	if project_names:
		for p in frappe.db.get_all(
			"Project",
			filters={"name": ("in", project_names)},
			fields=["name", "project_name", "custom_project_lead"],
		):
			lead_map[p.name] = p.custom_project_lead
			label_map[p.name] = p.project_name or p.name

	out = []
	for row in rows:
		if not hr and row.project not in lead_projects:
			continue
		logs = frappe.db.get_all(
			"Timesheet Detail",
			filters={"parent": row.timesheet, "project": row.project},
			fields=["hours", "from_time"],
		)
		logs = [l for l in logs if l.from_time]
		out.append(
			{
				"approval_name": row.approval_name,
				"timesheet": row.timesheet,
				"project": row.project,
				"project_lead": lead_map.get(row.project),
				"week_start": row.week_start,
				"week_end": row.week_end,
				"employee": row.employee,
				"employee_name": row.employee_name,
				"hours": round(sum(flt(l.hours) for l in logs), 2),
				"log_count": len(logs),
				"project_status": row.project_status,
				"hr_status": row.hr_status,
				"submitted_at": row.submitted_at,
				"modified": row.modified,
			}
		)
	return out
