import re

import frappe
from frappe import _
from frappe.model.document import Document


class EmployeeBookingSettings(Document):
	def before_insert(self) -> None:
		if not self.booking_slug:
			self.booking_slug = self._generate_slug()

	def validate(self) -> None:
		self._validate_slug()

	def _generate_slug(self) -> str:
		name = frappe.db.get_value("Employee", self.employee, "employee_name") or self.employee
		slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
		base, suffix = slug, 2
		while frappe.db.exists("Employee Booking Settings", {"booking_slug": slug, "name": ("!=", self.name or "")}):
			slug = f"{base}-{suffix}"
			suffix += 1
		return slug

	def _validate_slug(self) -> None:
		if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$", self.booking_slug):
			frappe.throw(_("Booking slug must be lowercase letters, numbers, and hyphens only"))

		existing = frappe.db.get_value(
			"Employee Booking Settings",
			{"booking_slug": self.booking_slug, "name": ("!=", self.name or "")},
			"employee_name",
		)
		if existing:
			frappe.throw(_("Booking slug '{0}' is already taken by {1}").format(self.booking_slug, existing))
