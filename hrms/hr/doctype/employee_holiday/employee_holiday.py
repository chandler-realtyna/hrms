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

	def before_save(self):
		"""Capture the previous status so on_update can detect transitions."""
		self._prev_status = (
			frappe.db.get_value("Employee Holiday", self.name, "status")
			if not self.is_new()
			else None
		)

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
		"""Send email notifications and create holiday list on approval."""
		prev = getattr(self, "_prev_status", None)

		if self.status == "Submitted" and prev != "Submitted":
			_notify_hr_holiday_submission(self)

		elif self.status == "Approved" and prev != "Approved":
			if not self.holiday_list:
				self._create_holiday_list()
			_notify_employee_holiday_approved(self)

		elif self.status == "Rejected" and prev != "Rejected":
			_notify_employee_holiday_rejected(self)

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


# ── Email notifications ───────────────────────────────────────────────────────


def _notify_hr_holiday_submission(doc):
	"""Email all HR Managers when an employee submits their holiday selection."""
	hr_emails = _get_hr_emails()
	if not hr_emails:
		return

	desk_url = frappe.utils.get_url(f"/app/employee-holiday/{doc.name}")
	subject = f"[HRMS] Holiday Request Submitted – {doc.employee_name} ({doc.year})"
	message = f"""
	<p>Hello,</p>
	<p><b>{doc.employee_name}</b> has submitted their personal holiday selection for <b>{doc.year}</b>
	and is awaiting your approval.</p>
	<p>
		<a href="{desk_url}" style="background:#3b82f6;color:#fff;padding:8px 18px;
		border-radius:6px;text-decoration:none;font-weight:600;">Review Request</a>
	</p>
	<p style="color:#6b7280;font-size:13px;">
		Record: {doc.name} &nbsp;·&nbsp; Employee: {doc.employee}
	</p>
	"""
	frappe.sendmail(recipients=hr_emails, subject=subject, message=message)


def _notify_employee_holiday_approved(doc):
	"""Email the employee when their holiday request is approved."""
	email = _get_employee_email(doc.employee)
	if not email:
		return

	subject = f"[HRMS] Your Holiday Request for {doc.year} has been Approved ✓"
	hl_note = (
		f"<p>Your personal holiday list <b>{doc.holiday_list}</b> has been created.</p>"
		if doc.holiday_list
		else ""
	)
	message = f"""
	<p>Hi {doc.employee_name},</p>
	<p>Your holiday selection for <b>{doc.year}</b> has been <b style="color:#16a34a;">approved</b>.</p>
	{hl_note}
	<p style="color:#6b7280;font-size:13px;">If you have any questions, please contact HR.</p>
	"""
	frappe.sendmail(recipients=[email], subject=subject, message=message)


def _notify_employee_holiday_rejected(doc):
	"""Email the employee when their holiday request is rejected."""
	email = _get_employee_email(doc.employee)
	if not email:
		return

	subject = f"[HRMS] Your Holiday Request for {doc.year} has been Rejected"
	message = f"""
	<p>Hi {doc.employee_name},</p>
	<p>Your holiday selection for <b>{doc.year}</b> has been <b style="color:#dc2626;">rejected</b>.</p>
	<p>Please contact HR for more information or to re-submit a revised selection.</p>
	<p style="color:#6b7280;font-size:13px;">Record: {doc.name}</p>
	"""
	frappe.sendmail(recipients=[email], subject=subject, message=message)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _get_hr_emails():
	"""Return a deduplicated list of email addresses for all HR Manager users."""
	rows = frappe.get_all(
		"Has Role",
		filters={"role": "HR Manager", "parenttype": "User"},
		fields=["parent"],
	)
	emails = []
	seen = set()
	for r in rows:
		email = frappe.db.get_value("User", r["parent"], "email")
		if email and email not in seen and r["parent"] not in ("Guest", "Administrator"):
			emails.append(email)
			seen.add(email)
	return emails


def _get_employee_email(employee):
	"""Return the email address for the given employee."""
	user_id = frappe.db.get_value("Employee", employee, "user_id")
	if not user_id:
		return None
	return frappe.db.get_value("User", user_id, "email") or user_id


def _is_hr_or_admin():
	"""Return True if the current user has an HR or admin role."""
	hr_roles = {"HR Manager", "HR User", "System Manager", "Administrator"}
	return bool(hr_roles & set(frappe.get_roles(frappe.session.user)))
