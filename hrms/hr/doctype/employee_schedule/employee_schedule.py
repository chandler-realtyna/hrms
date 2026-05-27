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

	def before_save(self):
		"""Capture the previous status so on_update can detect transitions."""
		self._prev_status = (
			frappe.db.get_value("Employee Schedule", self.name, "status")
			if not self.is_new()
			else None
		)

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

	# ── Hooks ───────────────────────────────────────────────────────────────

	def on_update(self):
		"""Send email notifications on status transitions."""
		prev = getattr(self, "_prev_status", None)

		if self.status == "Submitted" and prev != "Submitted":
			_notify_hr_schedule_submission(self)
		elif self.status == "Approved" and prev != "Approved":
			_notify_employee_schedule_approved(self)
		elif self.status == "Rejected" and prev != "Rejected":
			_notify_employee_schedule_rejected(self)


# ── Email notifications ───────────────────────────────────────────────────────


def _notify_hr_schedule_submission(doc):
	"""Email all HR Managers when an employee submits their work schedule."""
	hr_emails = _get_hr_emails()
	if not hr_emails:
		return

	desk_url = frappe.utils.get_url(f"/app/employee-schedule/{doc.name}")
	subject = f"[HRMS] Work Schedule Submitted – {doc.employee_name} ({doc.year})"
	message = f"""
	<p>Hello,</p>
	<p><b>{doc.employee_name}</b> has submitted their weekly work schedule for <b>{doc.year}</b>
	(timezone: {doc.timezone or "America/New_York"}) and is awaiting your approval.</p>
	<p>
		<a href="{desk_url}" style="background:#3b82f6;color:#fff;padding:8px 18px;
		border-radius:6px;text-decoration:none;font-weight:600;">Review Schedule</a>
	</p>
	<p style="color:#6b7280;font-size:13px;">
		Record: {doc.name} &nbsp;·&nbsp; Employee: {doc.employee}
	</p>
	"""
	frappe.sendmail(recipients=hr_emails, subject=subject, message=message)


def _notify_employee_schedule_approved(doc):
	"""Email the employee when their schedule is approved."""
	email = _get_employee_email(doc.employee)
	if not email:
		return

	subject = f"[HRMS] Your Work Schedule for {doc.year} has been Approved ✓"
	message = f"""
	<p>Hi {doc.employee_name},</p>
	<p>Your weekly work schedule for <b>{doc.year}</b> has been
	<b style="color:#16a34a;">approved</b>.</p>
	<p>Your schedule is now visible in the team availability view.</p>
	<p style="color:#6b7280;font-size:13px;">If you have any questions, please contact HR.</p>
	"""
	frappe.sendmail(recipients=[email], subject=subject, message=message)


def _notify_employee_schedule_rejected(doc):
	"""Email the employee when their schedule is rejected."""
	email = _get_employee_email(doc.employee)
	if not email:
		return

	subject = f"[HRMS] Your Work Schedule for {doc.year} has been Rejected"
	message = f"""
	<p>Hi {doc.employee_name},</p>
	<p>Your weekly work schedule for <b>{doc.year}</b> has been
	<b style="color:#dc2626;">rejected</b>.</p>
	<p>Please contact HR for more information or update and re-submit your schedule.</p>
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
	hr_roles = {"HR Manager", "HR User", "System Manager", "Administrator"}
	return bool(hr_roles & set(frappe.get_roles(frappe.session.user)))
