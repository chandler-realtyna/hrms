from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


FINAL_STATES = {"Approved for Payment", "Paid", "Cancelled"}


class EmployeeInvoice(Document):
	def before_insert(self):
		if not self.flags.invoice_api_action:
			frappe.throw(_("Invoices must be created through the HRMS invoice workflow."), frappe.PermissionError)

	def validate(self):
		if not self.is_new() and not self.flags.invoice_api_action:
			frappe.throw(_("Invoices must be changed through the HRMS invoice workflow."), frappe.PermissionError)
		if getdate(self.period_start) > getdate(self.period_end):
			frappe.throw(_("Period start cannot be after period end."))
		if getdate(self.due_date) < getdate(self.period_start):
			frappe.throw(_("Due date cannot be before the invoice period."))
		if flt(self.due_hours) < 0:
			frappe.throw(_("Due hours cannot be negative."))
		self._protect_paid_invoice()
		self._prevent_overlap()

	def _protect_paid_invoice(self):
		before = self.get_doc_before_save()
		if before and before.status == "Paid" and not self.flags.ignore_paid_protection:
			frappe.throw(_("A paid invoice cannot be changed."))

	def _prevent_overlap(self):
		if self.status in {"Draft", "Cancelled"}:
			return
		filters = {
			"employee": self.employee,
			"status": ("not in", ["Draft", "Cancelled"]),
			"period_start": ("<=", self.period_end),
			"period_end": (">=", self.period_start),
		}
		for name in frappe.get_all("Employee Invoice", filters=filters, pluck="name"):
			if name != self.name:
				frappe.throw(_("Invoice period overlaps with {0}.").format(frappe.bold(name)))

	def on_trash(self):
		if self.status != "Draft":
			frappe.throw(_("Only draft invoices can be deleted."))
