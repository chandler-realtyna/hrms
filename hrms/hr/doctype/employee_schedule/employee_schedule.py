# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class EmployeeSchedule(Document):
	def validate(self):
		self.validate_schedule_days()
		self.validate_duplicate_submission()
		self.validate_status_transition()

	def before_insert(self):
		"""Pre-fill Mon–Fri with one Working slot 09:00–17:00 if child table is empty."""
		if not self.schedule_days:
			for i, name in enumerate(DAY_NAMES):
				if i < 5:  # Mon–Fri only; weekends default to no slots (= Off)
					self.append(
						"schedule_days",
						{
							"day_of_week": i,
							"day_name": name,
							"day_type": "Working",
							"start_time": "09:00:00",
							"end_time": "17:00:00",
						},
					)

	def validate_schedule_days(self):
		if not self.schedule_days:
			return
		for row in self.schedule_days:
			# Keep day_name in sync
			if row.day_of_week is not None:
				row.day_name = DAY_NAMES[int(row.day_of_week)]
			# Working / On-Call slots must have start & end times
			if row.day_type in ("Working", "On-Call"):
				if not row.start_time or not row.end_time:
					frappe.throw(
						_("{0}: Start Time and End Time are required for {1} slots.").format(
							row.day_name, row.day_type
						)
					)

	def validate_duplicate_submission(self):
		filters = {
			"employee": self.employee,
			"year": self.year,
			"status": ["not in", ["Rejected"]],
		}
		if not self.is_new():
			filters["name"] = ["!=", self.name]
		existing = frappe.db.exists("Employee Schedule", filters)
		if existing:
			frappe.throw(
				_("A schedule for {0} in {1} already exists: {2}").format(
					self.employee_name, self.year, existing
				)
			)

	def validate_status_transition(self):
		if self.is_new():
			return
		if self.status in ("Approved", "Rejected") and not _is_hr_or_admin():
			frappe.throw(_("Only HR can approve or reject schedules."))
		old_status = frappe.db.get_value("Employee Schedule", self.name, "status")
		if old_status in ("Submitted", "Approved") and not _is_hr_or_admin():
			frappe.throw(_("You cannot modify a {0} schedule.").format(old_status))


def _is_hr_or_admin():
	hr_roles = {"HR Manager", "HR User", "System Manager", "Administrator"}
	return bool(hr_roles & set(frappe.get_roles(frappe.session.user)))
