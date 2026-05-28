import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class MeetingBooking(Document):
	def after_insert(self) -> None:
		self._create_calendar_event()
		self._send_confirmation_emails()

	def on_update(self) -> None:
		if self.status == "Cancelled" and self.frappe_event:
			self._cancel_calendar_event()
			self._send_cancellation_emails()

	def _create_calendar_event(self) -> None:
		host_user = frappe.db.get_value("Employee", self.host_employee, "user_id")
		if not host_user:
			return

		gcal_name = frappe.db.get_value("Google Calendar", {"user": host_user}, "name")

		event = frappe.new_doc("Event")
		event.subject = self.title
		event.description = self.description or ""
		event.starts_on = get_datetime(self.start_datetime)
		event.ends_on = get_datetime(self.end_datetime)
		event.event_type = "Private"

		if gcal_name:
			event.sync_with_google_calendar = 1
			event.google_calendar = gcal_name

		event.append(
			"event_participants",
			{"reference_doctype": "User", "reference_docname": host_user},
		)

		event.insert(ignore_permissions=True)
		self.db_set("frappe_event", event.name, update_modified=False)

	def _cancel_calendar_event(self) -> None:
		if not self.frappe_event:
			return
		try:
			frappe.delete_doc("Event", self.frappe_event, ignore_permissions=True)
		except Exception:
			pass
		self.db_set("frappe_event", None, update_modified=False)

	def _send_confirmation_emails(self) -> None:
		host_user_email = frappe.db.get_value("Employee", self.host_employee, "user_id")
		start_str = frappe.utils.format_datetime(self.start_datetime, "EEE, MMM d yyyy h:mm a")

		frappe.sendmail(
			recipients=[self.booker_email],
			subject=_("Meeting Confirmed: {0}").format(self.title),
			message=_(
				"Your meeting <b>{title}</b> with {host} is confirmed for <b>{start}</b>.<br><br>"
				"If you need to cancel, please contact {host_email}."
			).format(
				title=self.title,
				host=self.host_employee_name,
				start=start_str,
				host_email=host_user_email or "",
			),
		)

		if host_user_email:
			frappe.sendmail(
				recipients=[host_user_email],
				subject=_("New Booking: {0}").format(self.title),
				message=_(
					"<b>{name}</b> ({email}) has booked a meeting with you:<br><br>"
					"<b>Title:</b> {title}<br>"
					"<b>Time:</b> {start}<br>"
					"<b>Notes:</b> {desc}"
				).format(
					name=self.booker_name,
					email=self.booker_email,
					title=self.title,
					start=start_str,
					desc=self.description or "-",
				),
			)

	def _send_cancellation_emails(self) -> None:
		host_user_email = frappe.db.get_value("Employee", self.host_employee, "user_id")
		start_str = frappe.utils.format_datetime(self.start_datetime, "EEE, MMM d yyyy h:mm a")

		for recipient in filter(None, [self.booker_email, host_user_email]):
			frappe.sendmail(
				recipients=[recipient],
				subject=_("Meeting Cancelled: {0}").format(self.title),
				message=_("The meeting <b>{0}</b> scheduled for <b>{1}</b> has been cancelled.").format(
					self.title, start_str
				),
			)
