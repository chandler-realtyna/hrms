import frappe
from frappe.model.document import Document


class BookingLink(Document):
	"""Single-use public booking token. Only the token hash is stored; the
	full token is shown to the owner once at creation and never again."""

	def validate(self) -> None:
		if self.used and not self.used_at:
			self.used_at = frappe.utils.now_datetime()
