import frappe
from frappe import _


ON_BEHALF_ROLES = {"HR Manager", "HR User", "System Manager", "Company Desk Administrator"}


def validate_claimant(doc):
	old = doc.get_doc_before_save() if not doc.is_new() else None
	if old and old.employee != doc.employee:
		frappe.throw(_("The employee on a saved expense claim cannot be changed."), frappe.PermissionError)
	privileged = frappe.session.user == "Administrator" or bool(ON_BEHALF_ROLES.intersection(frappe.get_roles()))
	if doc.is_new() and not privileged:
		user = frappe.db.get_value("Employee", doc.employee, "user_id")
		if user != frappe.session.user:
			frappe.throw(_("You can only create expense claims for yourself."), frappe.PermissionError)
	if old and not privileged and old.company != doc.company:
		frappe.throw(_("The company on a saved expense claim cannot be changed."), frappe.PermissionError)
