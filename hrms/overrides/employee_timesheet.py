# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from frappe.utils.data import flt

from erpnext.projects.doctype.timesheet.timesheet import Timesheet


class EmployeeTimesheet(Timesheet):
	def validate(self):
		from hrms.api.weekly_timesheet import prepare_weekly_document, validate_weekly_document

		prepare_weekly_document(self)
		super().validate()
		validate_weekly_document(self)

	def before_submit(self):
		from hrms.api.weekly_timesheet import before_weekly_submit

		before_weekly_submit(self)

	def before_cancel(self):
		from hrms.api.weekly_timesheet import before_weekly_cancel

		before_weekly_cancel(self)
		super().before_cancel()

	def before_update_after_submit(self):
		from hrms.api.weekly_timesheet import before_weekly_update_after_submit

		before_weekly_update_after_submit(self)

	def set_status(self):
		self.status = {"0": "Draft", "1": "Submitted", "2": "Cancelled"}[str(self.docstatus or 0)]

		if flt(self.per_billed, self.precision("per_billed")) >= 100.0:
			self.status = "Billed"

		if 0.0 < flt(self.per_billed, self.precision("per_billed")) < 100.0:
			self.status = "Partially Billed"

		if self.salary_slip:
			self.status = "Payslip"

		if self.sales_invoice and self.salary_slip:
			self.status = "Completed"
