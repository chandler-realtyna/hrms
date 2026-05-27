"""
hrms.setup package

Python resolves `hrms.setup` to this package (hrms/setup/) rather than to the
sibling hrms/setup.py module, because packages take precedence over same-named
modules.  The canonical install/migrate helpers still live in hrms/setup.py, but
hooks.py references them as `hrms.setup.<function>`, so we re-export the symbols
here so the dotted paths remain valid.
"""

import frappe


# ---------------------------------------------------------------------------
# Re-exported from hrms/setup.py (shadowed by this package)
# ---------------------------------------------------------------------------

def update_select_perm_after_install():
	"""
	Re-export required by hooks.py → after_migrate.

	Called by Frappe after every `bench migrate`.  Updates the Select
	permission cache for all non-standard User Types so that field-level
	select-perm changes made during the migration take effect immediately.
	"""
	if not frappe.flags.update_select_perm_after_migrate:
		return

	frappe.flags.ignore_select_perm = False
	for row in frappe.get_all("User Type", filters={"is_standard": 0}):
		print("Updating user type :- ", row.name)
		doc = frappe.get_doc("User Type", row.name)
		doc.flags.ignore_links = True
		doc.save()

	frappe.flags.update_select_perm_after_migrate = False
