# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class EmployeeHoliday(Document):
	def validate(self):
		self.validate_dates()
		self.validate_duplicate_submission()
		self.validate_status_transition()

	# ── Validation helpers ──────────────────────────────────────────────────

	def validate_dates(self):
		if not self.holidays:
			return

		# No duplicate dates within the table
		dates = [h.date for h in self.holidays]
		if len(dates) != len(set(str(d) for d in dates)):
			frappe.throw(_("Duplicate dates found in the holiday list."))

		# All dates must fall in the declared year
		for h in self.holidays:
			if getdate(h.date).year != int(self.year):
				frappe.throw(
					_("Date {0} does not belong to year {1}.").format(h.date, self.year)
				)

		# When submitting enforce exactly 15
		if self.status == "Submitted" and len(self.holidays) != 15:
			frappe.throw(
				_("You must select exactly 15 holiday dates before submitting. Currently selected: {0}").format(
					len(self.holidays)
				)
			)

	def validate_duplicate_submission(self):
		"""Prevent two active (non-Rejected) records for the same employee/year."""
		filters = {
			"employee": self.employee,
			"year": self.year,
			"status": ["not in", ["Rejected"]],
		}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		existing = frappe.db.exists("Employee Holiday", filters)
		if existing:
			frappe.throw(
				_("A holiday record for {0} in {1} already exists: {2}").format(
					self.employee_name, self.year, existing
				)
			)

	def validate_status_transition(self):
		"""Only HR roles may set status to Approved / Rejected."""
		if self.is_new():
			return

		if self.status in ("Approved", "Rejected") and not _is_hr_or_admin():
			frappe.throw(_("Only HR can approve or reject holiday requests."))

		# Employees cannot edit a Submitted or Approved record
		old_status = frappe.db.get_value("Employee Holiday", self.name, "status")
		if old_status in ("Submitted", "Approved") and not _is_hr_or_admin():
			frappe.throw(
				_("You cannot modify a {0} holiday request.").format(old_status)
			)

	# ── Hooks ───────────────────────────────────────────────────────────────

	def on_update(self):
		"""Auto-create the Holiday List the first time the record is approved."""
		if self.status == "Approved" and not self.holiday_list:
			self._create_holiday_list()

	# ── Business logic ───────────────────────────────────────────────────────

	def _create_holiday_list(self):
		"""Create (or rebuild) a per-employee Holiday List and link it here."""
		hl_name = f"{self.employee_name} - {self.year}"

		if frappe.db.exists("Holiday List", hl_name):
			hl = frappe.get_doc("Holiday List", hl_name)
			hl.set("holidays", [])
		else:
			hl = frappe.new_doc("Holiday List")
			hl.holiday_list_name = hl_name
			hl.from_date = f"{self.year}-01-01"
			hl.to_date = f"{self.year}-12-31"

		for h in sorted(self.holidays, key=lambda x: x.date):
			hl.append(
				"holidays",
				{
					"holiday_date": h.date,
					"description": h.description or "Holiday",
					"weekly_off": 0,
				},
			)

		hl.save(ignore_permissions=True)

		# Persist the link without triggering a recursive save
		self.holiday_list = hl_name
		frappe.db.set_value(
			"Employee Holiday", self.name, "holiday_list", hl_name, update_modified=False
		)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_hr_or_admin():
	"""Return True if the current user has an HR or admin role."""
	hr_roles = {"HR Manager", "HR User", "System Manager", "Administrator"}
	return bool(hr_roles & set(frappe.get_roles(frappe.session.user)))
