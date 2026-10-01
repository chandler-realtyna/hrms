import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hrms.utils.company_desk import ARCHIVE_FIELD, ROLE, sync_director_scope


def execute():
	create_custom_fields({"User": [{"fieldname": ARCHIVE_FIELD, "label": "Original Company Desk Scope", "fieldtype": "Long Text", "hidden": 1, "read_only": 1, "no_copy": 1, "permlevel": 2}]}, update=True)
	users = {row.parent for row in frappe.get_all("Has Role", filters={"role": ROLE, "parenttype": "User"}, fields=["parent"])}
	for name in users:
		sync_director_scope(frappe.get_doc("User", name))
