import frappe


def publish_week_change(doc, method=None):
	# Notify only the employee here. Reviewer queues retain their permission-
	# scoped polling, avoiding disclosure through broad realtime broadcasts.
	user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if user:
		frappe.publish_realtime("hrms:week_changed", {"name": doc.name}, user=user, after_commit=True)
