"""Permission gates for the existing native holiday and schedule review APIs."""
import frappe


def get_personal_review_doc(doctype, name, permission="read"):
	if doctype not in {"Employee Holiday", "Employee Schedule"}:
		frappe.throw("Unsupported review document", frappe.PermissionError)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission(permission)
	# These doctypes do not carry company. Check the linked employee instead,
	# so Company/Employee user permissions still apply to name-based API calls.
	employee = frappe.get_doc("Employee", doc.employee)
	employee.check_permission("read")
	if employee.company:
		frappe.get_doc("Company", employee.company).check_permission("read")
	return doc
