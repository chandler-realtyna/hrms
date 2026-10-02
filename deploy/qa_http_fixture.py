"""Synthetic browser accounts, never run against production."""
import os
import frappe
from frappe.utils.password import update_password

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="qa.local", sites_path=".")
frappe.connect()
assert frappe.local.site == "qa.local"
frappe.set_user("Administrator")
frappe.db.set_single_value("System Settings", "setup_complete", 1)
frappe.db.set_value("Installed Application", {"app_name": ("in", ["frappe", "erpnext"])}, "is_setup_complete", 1)
frappe.clear_cache()
for user in ("worker@qa.invalid", "lead@qa.invalid", "hr@qa.invalid"):
	update_password(user, "Synthetic-QA-Only!9842-Browser")
	frappe.db.delete("HRMS Work State Operation", {"user": user})
	frappe.db.delete("HRMS Work State", {"user": user})
worker = frappe.db.get_value("Employee", {"user_id": "worker@qa.invalid"}, "name")
assert worker, "Synthetic worker fixture must exist before browser acceptance"
frappe.db.set_value("Employee", worker, {
	"custom_invoice_calculation_method": "Fixed Monthly",
	"custom_invoice_currency": "USD",
	"custom_invoice_payee_name": "Synthetic Contractor",
	"custom_preferred_payment_method": "Bank Transfer",
	"custom_monthly_invoice_amount": 1000,
})
frappe.db.commit()
frappe.destroy()
