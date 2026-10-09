import frappe
from frappe.model.document import Document


class HRMSWorkState(Document):
	def validate(self):
		if not frappe.local.flags.get("hrms_work_state_write"):
			frappe.throw("Use the authenticated work-state API.", frappe.PermissionError)
