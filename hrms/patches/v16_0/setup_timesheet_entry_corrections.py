from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Timesheet": [{
				"fieldname": "custom_correction_scope",
				"label": "Correction Scope",
				"fieldtype": "Long Text",
				"insert_after": "custom_weekly_return_reason",
				"hidden": 1,
				"read_only": 1,
			}],
			"Timesheet Detail": [{
				"fieldname": "custom_return_reason",
				"label": "Correction Reason",
				"fieldtype": "Small Text",
				"insert_after": "description",
				"read_only": 1,
			}],
		},
		update=True,
	)
