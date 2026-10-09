import frappe
from frappe import _


MANAGER_ROLES = {"HR Manager", "HR User", "System Manager", "Company Desk Administrator"}
APPROVER_FIELDS = {"Leave Application": "leave_approver", "Expense Claim": "expense_approver"}


def _is_manager(user):
	return user == "Administrator" or bool(MANAGER_ROLES.intersection(frappe.get_roles(user)))


def _condition(doctype, user=None):
	user = user or frappe.session.user
	if _is_manager(user):
		return ""
	escaped = frappe.db.escape(user)
	field = "name" if doctype == "Employee" else "employee"
	condition = f"`tab{doctype}`.`{field}` IN (SELECT name FROM `tabEmployee` WHERE user_id = {escaped})"
	if approver := APPROVER_FIELDS.get(doctype):
		condition = f"({condition} OR `tab{doctype}`.`{approver}` = {escaped})"
	return condition


def employee_query(user=None):
	return _condition("Employee", user)


def schedule_query(user=None):
	return _condition("Employee Schedule", user)


def holiday_query(user=None):
	return _condition("Employee Holiday", user)


def timesheet_query(user=None):
	return _condition("Timesheet", user)


def leave_query(user=None):
	return _condition("Leave Application", user)


def expense_query(user=None):
	return _condition("Expense Claim", user)


def has_personal_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if _is_manager(user):
		return True
	if doc.doctype == "Employee" and ptype not in {None, "read", "print", "email"}:
		return False
	if approver := APPROVER_FIELDS.get(doc.doctype):
		if doc.get(approver) == user:
			return True
	employee = doc.name if doc.doctype == "Employee" else doc.get("employee")
	if not employee or frappe.db.get_value("Employee", employee, "user_id") != user:
		return False
	# Controller hooks can only deny access. Frappe v16 treats None as denial;
	# True preserves the role and user-permission checks performed by Frappe.
	return True


def validate_personal_request(doc):
	old = doc.get_doc_before_save() if not doc.is_new() else None
	if old and old.employee != doc.employee:
		frappe.throw(_("The employee on a saved request cannot be changed."), frappe.PermissionError)
	if _is_manager(frappe.session.user):
		return
	if frappe.db.get_value("Employee", doc.employee, "user_id") != frappe.session.user:
		frappe.throw(_("You can only save your own requests."), frappe.PermissionError)
	if doc.is_new() and doc.status not in {"Draft", "Submitted"}:
		frappe.throw(_("Only HR can approve or reject requests."), frappe.PermissionError)
