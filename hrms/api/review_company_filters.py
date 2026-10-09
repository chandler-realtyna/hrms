"""Company choices for native HR review lists; never bypass list permissions."""
import frappe

from hrms.utils.personal_scope import _is_manager


REVIEW_DOCTYPES = {
	"Leave Application", "Expense Claim", "Employee Invoice",
	"Employee Holiday", "Employee Schedule",
}


@frappe.whitelist()
def get_review_companies(doctype):
	if doctype not in REVIEW_DOCTYPES or not _is_manager(frappe.session.user):
		frappe.throw("Not permitted", frappe.PermissionError)
	if not frappe.has_permission(doctype, "read"):
		frappe.throw("Not permitted", frappe.PermissionError)
	companies = frappe.get_list("Company", fields=["name"], order_by="name asc", limit_page_length=5000)
	names = [row.name for row in companies]
	employees = []
	if names and frappe.has_permission("Employee", "read"):
		employees = frappe.get_list(
			"Employee", fields=["name", "company"], filters={"company": ["in", names]},
			order_by="name asc", limit_page_length=0,
		)
	return {
		"companies": names,
		"employee_companies": {row.name: row.company for row in employees},
	}
