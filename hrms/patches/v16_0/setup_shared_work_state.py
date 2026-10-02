import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({"HR Settings": [{"fieldname": "custom_employee_leave_approver", "label": "Employee Leave Approver", "fieldtype": "Link", "options": "User", "insert_after": "leave_approver_mandatory_in_leave_application"}]}, update=True)
	if not frappe.db.get_single_value("HR Settings", "custom_employee_leave_approver") and frappe.db.exists("User", "hr@realtyna.com"):
		frappe.db.set_single_value("HR Settings", "custom_employee_leave_approver", "hr@realtyna.com")
