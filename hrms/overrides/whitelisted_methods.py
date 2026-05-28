import frappe
from frappe import _

# Fields from System Settings that are safe to expose to all logged-in users.
# These are pure formatting/locale values — no credentials, no sensitive config.
_SAFE_SYSTEM_SETTINGS_FIELDS = frozenset(
	[
		"number_format",
		"currency",
		"currency_precision",
		"float_precision",
		"date_format",
		"time_format",
		"first_day_of_the_week",
		"country",
		"language",
	]
)


@frappe.whitelist()
def get_single_value(doctype: str, field: str):
	"""
	Override of ``frappe.client.get_single_value``.

	frappe-ui's currency/number formatter calls this method to fetch
	``System Settings.number_format`` on every page load.  The standard
	Frappe implementation throws a PermissionError when the requesting
	user (e.g. an Employee) does not have read permission on
	System Settings.

	Rather than granting blanket System Settings read access to the
	Employee role, we allow the small set of non-sensitive formatting
	fields listed in ``_SAFE_SYSTEM_SETTINGS_FIELDS`` to be read by any
	authenticated user.  Everything else falls through to the standard
	permission check.
	"""
	if doctype == "System Settings" and field in _SAFE_SYSTEM_SETTINGS_FIELDS:
		return frappe.db.get_single_value(doctype, field)

	# Standard path — will raise PermissionError for anything sensitive
	if not frappe.has_permission(doctype):
		frappe.throw(_("No permission for {0}").format(_(doctype)), frappe.PermissionError)

	return frappe.db.get_single_value(doctype, field)
