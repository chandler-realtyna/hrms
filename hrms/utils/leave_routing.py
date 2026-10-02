import frappe
from frappe import _

FIELD = "custom_employee_leave_approver"


def default_approver():
	user = frappe.db.get_single_value("HR Settings", FIELD)
	if not user or not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("HR leave approval is not configured. Please contact HR."))
	if not {"HR Manager", "HR User", "Company Desk Administrator", "System Manager"}.intersection(frappe.get_roles(user)):
		frappe.throw(_("The configured leave approver must have an HR management role."))
	return user


def route_personal_leave(doc, method=None):
	if not doc.is_new() and doc.docstatus != 0:
		return
	if frappe.db.get_value("Employee", doc.employee, "user_id") != frappe.session.user:
		return
	doc.leave_approver = default_approver()
	doc.leave_approver_name = frappe.db.get_value("User", doc.leave_approver, "full_name")
