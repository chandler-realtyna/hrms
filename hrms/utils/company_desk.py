import frappe

from hrms.patches.v16_0.create_company_director_access import ROLE


ARCHIVE_FIELD = "custom_company_desk_scope_archive"
SCOPE_TYPES = ("Company", "Employee", "Project", "Department")
SCOPE_FIELDS = ("allow", "for_value", "applicable_for", "apply_to_all_doctypes", "is_default", "hide_descendants")


def _key(rule):
	return tuple(rule.get(field) for field in SCOPE_FIELDS[:4])


def sync_director_scope(user, method=None):
	if not user.meta.has_field(ARCHIVE_FIELD):
		return
	archive = frappe.parse_json(user.get(ARCHIVE_FIELD)) or []
	if ROLE in {row.role for row in user.roles}:
		rules = frappe.get_all("User Permission", filters={"user": user.name, "allow": ("in", SCOPE_TYPES)}, fields=["name", *SCOPE_FIELDS])
		if not rules:
			return
		keys = {_key(rule) for rule in archive}
		for rule in rules:
			if _key(rule) not in keys:
				archive.append(dict(rule))
				keys.add(_key(rule))
		# Keep the original scope before removing only these managerial filters.
		user.db_set(ARCHIVE_FIELD, frappe.as_json(archive), update_modified=False)
		for rule in rules:
			frappe.delete_doc("User Permission", rule.name, ignore_permissions=True)
	elif archive:
		for rule in archive:
			if not frappe.db.exists(rule["allow"], rule["for_value"]):
				continue
			filters = {"user": user.name, **{field: rule.get(field) for field in SCOPE_FIELDS[:4]}}
			if not frappe.db.exists("User Permission", filters):
				frappe.get_doc({"doctype": "User Permission", "user": user.name, **{field: rule.get(field) for field in SCOPE_FIELDS}}).insert(ignore_permissions=True)
		user.db_set(ARCHIVE_FIELD, None, update_modified=False)
	else:
		return
	frappe.clear_cache(user=user.name)


def sync_employee_director_scope(employee, method=None):
	if employee.user_id and frappe.db.exists("User", employee.user_id):
		sync_director_scope(frappe.get_doc("User", employee.user_id))
