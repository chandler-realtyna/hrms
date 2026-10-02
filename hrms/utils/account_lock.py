import frappe
from frappe import _


def lock_current_account():
	if frappe.session.user == "Guest":
		frappe.throw(_("Sign in to continue."), frappe.PermissionError)
	# Authentication may have established a repeatable-read snapshot before
	# another device commits. Restart only if there are no enclosing writes.
	if frappe.db.transaction_writes == 0:
		frappe.db.rollback()
	frappe.db.sql("SELECT name FROM tabUser WHERE name = %s FOR UPDATE", (frappe.session.user,))
