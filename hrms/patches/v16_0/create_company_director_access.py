import frappe
from frappe.permissions import add_permission, update_permission_property


ROLE = "Company Desk Administrator"
ROLE_PROFILE = "Company Directors"
INITIAL_USERS = (
	"giselle@realtyna.com",
	"hr@realtyna.com",
	"babak@realtyna.net",
	"ali@realtyna.com",
)
PERMISSIONS = {
	"Role": {"read": 1},
	"User": {"read": 1, "write": 1, "create": 1},
	"Employee": {"read": 1, "write": 1, "create": 1},
	"Project": {"read": 1, "write": 1, "create": 1},
}


def execute():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": ROLE, "desk_access": 1, "is_custom": 1}
		).insert(ignore_permissions=True)

	for doctype, permissions in PERMISSIONS.items():
		add_permission(doctype, ROLE)
		for permission, enabled in permissions.items():
			update_permission_property(
				doctype, ROLE, permlevel=0, ptype=permission, value=enabled
			)

	profile = (
		frappe.get_doc("Role Profile", ROLE_PROFILE)
		if frappe.db.exists("Role Profile", ROLE_PROFILE)
		else frappe.new_doc("Role Profile")
	)
	profile.role_profile = ROLE_PROFILE
	profile_roles = {row.role for row in profile.roles}
	for role in ("HR Manager", ROLE):
		if role not in profile_roles:
			profile.append("roles", {"role": role})
	profile.save(ignore_permissions=True)

	for email in INITIAL_USERS:
		user_name = frappe.db.get_value("User", email, "name")
		if not user_name:
			continue
		user = frappe.get_doc("User", user_name)
		assigned_roles = {row.role for row in user.roles}
		missing_roles = {"HR Manager", ROLE} - assigned_roles
		if missing_roles:
			user.add_roles(*sorted(missing_roles))
