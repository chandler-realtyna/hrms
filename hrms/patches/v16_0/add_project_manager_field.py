import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "custom_project_manager",
					"fieldtype": "Link",
					"label": "Project Manager",
					"options": "Employee",
					"insert_after": "custom_project_lead",
					"description": "Optional. Submitted project time is reviewed by this employee before HR.",
				}
			],
		},
		update=True,
	)
	frappe.clear_cache(doctype="Project")
	move_unmanaged_pending_reviews_to_hr()


def move_unmanaged_pending_reviews_to_hr():
	timesheets = frappe.get_all(
		"Timesheet",
		filters={
			"custom_is_weekly": 1,
			"custom_weekly_status": "Pending Project Approval",
			"docstatus": 0,
		},
		pluck="name",
		limit_page_length=0,
	)
	for timesheet in timesheets:
		employee = frappe.db.get_value("Timesheet", timesheet, "employee")
		employee_user = frappe.db.get_value("Employee", employee, "user_id")
		approvals = frappe.get_all(
			"Timesheet Project Approval",
			filters={"parent": timesheet, "status": "Pending"},
			fields=["name", "project"],
			limit_page_length=0,
		)
		for approval in approvals:
			manager = frappe.db.get_value("Project", approval.project, "custom_project_manager")
			manager_user = None
			if manager:
				manager_user = frappe.db.get_value(
					"Employee", {"name": manager, "status": "Active"}, "user_id"
				)
			status = "Pending" if manager_user and manager_user != employee_user else "HR Review"
			frappe.db.set_value(
				"Timesheet Project Approval",
				approval.name,
				{"controller": manager_user, "status": status},
				update_modified=False,
			)

		still_pending = frappe.db.exists(
			"Timesheet Project Approval", {"parent": timesheet, "status": "Pending"}
		)
		if not still_pending:
			frappe.db.set_value(
				"Timesheet",
				timesheet,
				"custom_weekly_status",
				"Pending HR Review",
				update_modified=False,
			)
