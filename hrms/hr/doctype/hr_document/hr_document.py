# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HRDocument(Document):
	def validate(self):
		if self.url and not self.url.startswith(("http://", "https://")):
			self.url = "https://" + self.url
