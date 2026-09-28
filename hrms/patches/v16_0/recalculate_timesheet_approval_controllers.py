"""Recalculate pending Timesheet Project Approval controllers using Project Lead.

History: approval rows used to point at the Project Manager. The weekly
workflow now approves via Project Lead, so pending rows are re-pointed:
  - active lead with a user account  -> controller = lead's user (stays Pending)
  - employee is their own lead, or no usable lead -> status = HR Review
    (routes to HR; controller left untouched since HR rows are not actionable
    via project review)

Approved rows and all history are preserved. Idempotent: re-running changes
nothing once controllers match the current leads.
"""

import frappe


def execute():
	from hrms.api.weekly_timesheet import (
		APPROVAL_APPROVED,
		APPROVAL_HR,
		APPROVAL_PENDING,
		_project_lead_employee,
		_project_lead_user,
	)

	pending = frappe.get_all(
		"Timesheet Project Approval",
		filters={"status": APPROVAL_PENDING},
		fields=["name", "parent", "project", "controller"],
	)
	fixed = 0
	rerouted = 0
	for approval in pending:
		try:
			doc = frappe.get_doc("Timesheet", approval.parent)
		except frappe.DoesNotExistError:
			continue
		if doc.docstatus != 0:
			continue
		controller = _project_lead_user(approval.project)
		lead_employee = _project_lead_employee(approval.project)
		if controller and lead_employee != doc.employee:
			if approval.controller != controller:
				frappe.db.set_value(
					"Timesheet Project Approval", approval.name, "controller", controller
				)
				fixed += 1
		else:
			frappe.db.set_value(
				"Timesheet Project Approval", approval.name, "status", APPROVAL_HR
			)
			rerouted += 1

	frappe.db.commit()
	print(f"recalculated {fixed} pending approval controllers, routed {rerouted} to HR review")
