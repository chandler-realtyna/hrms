import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Timesheet": [
				{
					"fieldname": "custom_is_weekly",
					"fieldtype": "Check",
					"label": "Weekly Timesheet",
					"insert_after": "end_date",
					"default": "0",
					"read_only": 1,
				},
				{
					"fieldname": "custom_week_start",
					"fieldtype": "Date",
					"label": "Week Start",
					"insert_after": "custom_is_weekly",
					"read_only": 1,
				},
				{
					"fieldname": "custom_week_end",
					"fieldtype": "Date",
					"label": "Week End",
					"insert_after": "custom_week_start",
					"read_only": 1,
				},
				{
					"fieldname": "custom_week_key",
					"fieldtype": "Data",
					"label": "Week Key",
					"insert_after": "custom_week_end",
					"hidden": 1,
					"read_only": 1,
					"unique": 1,
				},
				{
					"fieldname": "custom_weekly_status",
					"fieldtype": "Select",
					"label": "Weekly Approval Status",
					"insert_after": "custom_week_key",
					"options": "Draft\nPending Project Approval\nCorrection Required\nPending HR Review\nClosed",
					"read_only": 1,
				},
				{
					"fieldname": "custom_weekly_submitted_at",
					"fieldtype": "Datetime",
					"label": "Weekly Submitted At",
					"insert_after": "custom_weekly_status",
					"read_only": 1,
				},
				{
					"fieldname": "custom_weekly_closed_at",
					"fieldtype": "Datetime",
					"label": "Weekly Closed At",
					"insert_after": "custom_weekly_submitted_at",
					"read_only": 1,
				},
				{
					"fieldname": "custom_weekly_return_reason",
					"fieldtype": "Small Text",
					"label": "Return Reason",
					"insert_after": "custom_weekly_closed_at",
					"read_only": 1,
				},
				{
					"fieldname": "custom_project_approvals",
					"fieldtype": "Table",
					"label": "Project Approvals",
					"insert_after": "custom_weekly_return_reason",
					"options": "Timesheet Project Approval",
					"read_only": 1,
				},
			],
		},
		update=True,
	)

	frappe.db.set_value("DocType", "Timesheet", "track_changes", 1, update_modified=False)
	frappe.clear_cache(doctype="Timesheet")
