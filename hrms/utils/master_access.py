"""Explicit deny-only boundaries for the audited contractor master records."""
import frappe

from hrms.utils.personal_scope import _is_manager, _condition


def can_manage_master(doctype, user=None):
	user = user or frappe.session.user
	return _is_manager(user) or (doctype == "Project" and "Projects Manager" in frappe.get_roles(user))


def user_query(user=None):
	user = user or frappe.session.user
	return "" if _is_manager(user) else f"`tabUser`.`name` = {frappe.db.escape(user)}"


def user_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	return _is_manager(user) or (doc.name == user and ptype not in {"create", "delete", "share"})


def project_query(user=None):
	return "" if can_manage_master("Project", user) else "1=0"


def project_permission(doc, ptype=None, user=None):
	return can_manage_master("Project", user)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def project_lookup(doctype, txt, searchfield, start, page_len, filters=None, **kwargs):
	if not can_manage_master("Project"):
		from hrms.api import search_employee_projects
		return search_employee_projects("Project", txt, searchfield, start, page_len, filters or {})
	rows = frappe.get_list("Project", fields=["name", "project_name"], filters=filters or {},
		or_filters={"name": ["like", f"%{txt}%"], "project_name": ["like", f"%{txt}%"]},
		limit_start=start, limit_page_length=page_len, order_by="project_name asc")
	return [(row.name, row.project_name) for row in rows]


def booking_settings_query(user=None):
	return _condition("Employee Booking Settings", user)


def meeting_query(user=None):
	user = user or frappe.session.user
	if _is_manager(user):
		return ""
	value = frappe.db.escape(user)
	return f"(`tabMeeting Booking`.`host_employee` IN (SELECT name FROM `tabEmployee` WHERE user_id = {value}) OR `tabMeeting Booking`.`booker_email` = {value})"


def meeting_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	return _is_manager(user) or doc.get("booker_email") == user or frappe.db.get_value("Employee", doc.get("host_employee"), "user_id") == user


def activity_permission(doc, ptype=None, user=None):
	return _is_manager(user or frappe.session.user) or ptype in {None, "read", "print", "export"}
