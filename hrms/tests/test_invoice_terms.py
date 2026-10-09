"""Invoice acceptance on real Frappe documents; synthetic QA only."""
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import getdate

from hrms.api import employee_invoice as invoice
from hrms.tests.test_shared_work_state import TestSharedWorkState
from hrms.utils import invoice_terms


class TestInvoiceTerms(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		TestSharedWorkState.setUpClass.__func__(cls)

	def setUp(self):
		frappe.set_user(self.users[0])
		frappe.db.savepoint("invoice_terms_test")
		frappe.db.set_value("Employee", self.employees[0], {
			"custom_invoice_calculation_method": "Fixed Monthly",
			"custom_invoice_currency": "USD",
			"custom_invoice_payee_name": "Synthetic Contractor",
			"custom_preferred_payment_method": "Bank Transfer",
			"custom_monthly_invoice_amount": 1000,
		})
		self.clock = patch.object(invoice_terms, "nowdate", return_value="2026-10-02")
		self.clock.start()

	def tearDown(self):
		self.clock.stop()
		frappe.db.rollback(save_point="invoice_terms_test")
		frappe.set_user("Administrator")

	def create(self, **kwargs):
		return invoice.create_employee_invoice(**kwargs)

	def test_server_date_and_fifteen_calendar_days_across_boundaries(self):
		for issue, due in (("2026-10-02", "2026-10-17"), ("2026-12-25", "2027-01-09"),
			("2028-02-20", "2028-03-06"), ("2027-02-20", "2027-03-07")):
			with self.subTest(issue=issue), patch.object(invoice_terms, "nowdate", return_value=issue):
				self.assertEqual(invoice.get_invoice_defaults(), {"invoice_date": issue, "due_date": due})

	def test_create_ignores_legacy_caller_due_date(self):
		result = self.create(due_date="2099-01-01")
		self.assertEqual(result["invoice_date"], "2026-10-02")
		self.assertEqual(result["due_date"], "2026-10-17")
		self.assertEqual(result["period_end"], "2026-10-02")
		self.assertEqual(result["period_start"], "2026-09-02")
		self.assertEqual(str(frappe.get_doc("Employee Invoice", result["name"]).due_date), "2026-10-17")

	def test_personal_save_cannot_override_issue_or_due_date(self):
		result = self.create()
		saved = invoice.save_employee_invoice(result["name"], {
			"due_date": "2099-01-01", "invoice_date": "2098-12-17", "employee_note": "Synthetic note",
		})
		self.assertEqual(saved["invoice_date"], "2026-10-02")
		self.assertEqual(saved["due_date"], "2026-10-17")

	def test_document_validation_recomputes_due_date(self):
		result = self.create()
		doc = frappe.get_doc("Employee Invoice", result["name"])
		doc.due_date = "2099-01-01"
		invoice._persist(doc)
		self.assertEqual(getdate(doc.due_date), getdate("2026-10-17"))
		self.assertTrue(frappe.get_meta("Employee Invoice").get_field("due_date").read_only)

	def test_hr_changes_cannot_override_payment_terms(self):
		result = self.create()
		invoice.confirm_employee_invoice(result["name"])
		frappe.set_user(self.users[2])
		saved = invoice.hr_update_employee_invoice(result["name"], {
			"due_date": "2099-01-01", "invoice_date": "2098-12-17", "hr_note": "Synthetic HR note",
		}, reason="Synthetic review")
		self.assertEqual(saved["invoice_date"], "2026-10-02")
		self.assertEqual(saved["due_date"], "2026-10-17")

	def test_existing_final_financial_dates_are_not_rewritten(self):
		result = self.create()
		for status in ("Approved for Payment", "Paid", "Cancelled"):
			doc = frappe.get_doc("Employee Invoice", result["name"])
			doc.status = status
			doc.due_date = "2026-10-30"
			invoice_terms.apply_invoice_terms(doc)
			self.assertEqual(str(doc.due_date), "2026-10-30")

	def test_english_labels_preserve_schema_and_stored_status(self):
		previous = frappe.local.lang
		try:
			frappe.local.lang = "en"
			self.assertEqual(frappe._("Employee"), "Contractor")
			self.assertEqual(frappe._("Employee Invoice"), "Invoice")
			self.assertEqual(frappe._("Pending Employee Confirmation"), "Pending Contractor Confirmation")
			self.assertTrue(frappe.db.exists("DocType", "Employee"))
			self.assertTrue(frappe.db.exists("Role", "Employee"))
			self.assertIn("Pending Employee Confirmation", frappe.get_meta("Employee Invoice").get_field("status").options)
		finally:
			frappe.local.lang = previous

	def test_printed_invoice_heading_and_contractor_label(self):
		result = self.create()
		invoice.save_employee_invoice(result["name"], {"employee_note": "Synthetic note"})
		html = frappe.get_print("Employee Invoice", result["name"], print_format="Employee Invoice")
		self.assertIn("<h1>Invoice</h1>", html)
		self.assertIn("<strong>Contractor:</strong>", html)
		self.assertNotIn("<h1>Employee Invoice</h1>", html)
