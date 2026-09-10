from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate(filters)

	if cint(filters.preview_demo_data):
		rows, summary, chart = _demo_data()
		message = _(
			"You are viewing fictional preview data. No employee, timesheet, leave, expense, or invoice records were created."
		)
	else:
		rows, summary, chart = _live_data(filters)
		message = _("Live data for the selected company and period.")

	return _columns(), rows, message, chart, summary


def _validate(filters):
	if not filters.company:
		frappe.throw(_("Company is required."))
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("From Date and To Date are required."))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def _columns():
	return [
		{"fieldname": "area", "label": _("Area"), "fieldtype": "Data", "width": 150},
		{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 240},
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Float", "width": 110},
		{"fieldname": "unit", "label": _("Unit"), "fieldtype": "Data", "width": 100},
		{"fieldname": "status", "label": _("Management Status"), "fieldtype": "Data", "width": 150},
		{"fieldname": "context", "label": _("What it means"), "fieldtype": "Data", "width": 360},
	]


def _row(area, metric, value, unit, status, context):
	return {
		"area": area,
		"metric": metric,
		"value": flt(value, 2),
		"unit": unit,
		"status": status,
		"context": context,
	}


def _live_data(filters):
	company = filters.company
	period = {"company": company, "from_date": filters.from_date, "to_date": filters.to_date}

	active_employees = frappe.db.count("Employee", {"company": company, "status": "Active"})
	time_stats = frappe.db.sql(
		"""
		SELECT
			COALESCE(SUM(d.hours), 0) AS total_hours,
			COUNT(DISTINCT t.employee) AS employees_with_time,
			COUNT(DISTINCT CASE WHEN t.docstatus = 0 THEN t.name END) AS draft_timesheets,
			COUNT(DISTINCT CASE WHEN t.docstatus = 1 THEN t.name END) AS submitted_timesheets
		FROM `tabTimesheet` t
		INNER JOIN `tabTimesheet Detail` d ON d.parent = t.name
		WHERE t.company = %(company)s
		  AND t.docstatus < 2
		  AND DATE(d.from_time) BETWEEN %(from_date)s AND %(to_date)s
		""",
		period,
		as_dict=True,
	)[0]

	leave_pending = frappe.db.count(
		"Leave Application",
		{
			"company": company,
			"status": ("in", ["Open", "Pending"]),
			"from_date": ("<=", filters.to_date),
			"to_date": (">=", filters.from_date),
		},
	)
	leave_approved = frappe.db.count(
		"Leave Application",
		{
			"company": company,
			"status": "Approved",
			"from_date": ("<=", filters.to_date),
			"to_date": (">=", filters.from_date),
		},
	)
	expense_drafts = frappe.db.count("Expense Claim", {"company": company, "docstatus": 0})
	expense_unpaid = frappe.db.count("Expense Claim", {"company": company, "docstatus": 1, "is_paid": 0})

	invoice_counts = {
		row.status: row.count
		for row in frappe.db.sql(
			"""
			SELECT status, COUNT(name) AS count
			FROM `tabEmployee Invoice`
			WHERE company = %(company)s
			  AND invoice_date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY status
			""",
			period,
			as_dict=True,
		)
	}

	rows = [
		_row(_("Workforce"), _("Active employees"), active_employees, _("people"), _("Information"), _("Employees currently marked Active.")),
		_row(_("Time"), _("Hours logged"), time_stats.total_hours, _("hours"), _("Information"), _("All non-cancelled time logs in the selected period.")),
		_row(_("Time"), _("Employees with time"), time_stats.employees_with_time, _("people"), _("Information"), _("Employees who logged at least one entry.")),
		_row(_("Time"), _("Draft timesheets"), time_stats.draft_timesheets, _("records"), _("Needs review") if time_stats.draft_timesheets else _("Clear"), _("Saved but not submitted timesheets.")),
		_row(_("Time"), _("Submitted timesheets"), time_stats.submitted_timesheets, _("records"), _("Complete"), _("Submitted timesheets in the period.")),
		_row(_("Leave"), _("Pending leave requests"), leave_pending, _("requests"), _("Needs review") if leave_pending else _("Clear"), _("Leave applications waiting for a decision.")),
		_row(_("Leave"), _("Approved leave requests"), leave_approved, _("requests"), _("Information"), _("Approved leave overlapping this period.")),
		_row(_("Expenses"), _("Draft expense claims"), expense_drafts, _("claims"), _("Information"), _("Claims still being prepared.")),
		_row(_("Expenses"), _("Unpaid expense claims"), expense_unpaid, _("claims"), _("Needs payment") if expense_unpaid else _("Clear"), _("Submitted claims that are not yet paid.")),
	]

	for status in (
		"Pending HR Review",
		"Changes Requested",
		"Pending Employee Confirmation",
		"Approved for Payment",
		"Paid",
	):
		value = invoice_counts.get(status, 0)
		management_status = _("Complete") if status == "Paid" else _("Needs action") if value else _("Clear")
		rows.append(_row(_("Invoices"), _(status), value, _("invoices"), management_status, _invoice_context(status)))

	invoice_actions = sum(
		cint(invoice_counts.get(status, 0))
		for status in ("Pending HR Review", "Changes Requested", "Pending Employee Confirmation")
	)
	pending_actions = (
		cint(time_stats.draft_timesheets) + cint(leave_pending) + cint(expense_unpaid) + invoice_actions
	)
	approved_for_payment = cint(invoice_counts.get("Approved for Payment", 0))
	summary = _summary(active_employees, time_stats.total_hours, pending_actions, approved_for_payment)
	chart = _attention_chart(time_stats.draft_timesheets, leave_pending, expense_unpaid, invoice_actions)
	return rows, summary, chart


def _invoice_context(status):
	return {
		"Pending HR Review": _("Employee confirmed; HR review is next."),
		"Changes Requested": _("Employee must revise and resubmit."),
		"Pending Employee Confirmation": _("HR changed material values; employee confirmation is required."),
		"Approved for Payment": _("Approved and waiting for payment details."),
		"Paid": _("Payment was recorded and the invoice is final."),
	}[status]


def _demo_data():
	rows = [
		_row(_("Workforce"), _("Active employees"), 24, _("people"), _("Information"), _("Fictional team size.")),
		_row(_("Time"), _("Hours logged"), 736, _("hours"), _("Information"), _("Fictional total for the selected period.")),
		_row(_("Time"), _("Employees with time"), 21, _("people"), _("Needs review"), _("Three fictional employees have no time logged.")),
		_row(_("Time"), _("Draft timesheets"), 4, _("records"), _("Needs review"), _("Fictional drafts still being prepared.")),
		_row(_("Time"), _("Submitted timesheets"), 18, _("records"), _("Complete"), _("Fictional submitted timesheets.")),
		_row(_("Leave"), _("Pending leave requests"), 2, _("requests"), _("Needs review"), _("Fictional requests awaiting HR.")),
		_row(_("Leave"), _("Approved leave requests"), 3, _("requests"), _("Information"), _("Fictional approved leave.")),
		_row(_("Expenses"), _("Draft expense claims"), 2, _("claims"), _("Information"), _("Fictional employee drafts.")),
		_row(_("Expenses"), _("Unpaid expense claims"), 2, _("claims"), _("Needs payment"), _("Fictional approved claims awaiting reimbursement.")),
		_row(_("Invoices"), _("Pending HR Review"), 3, _("invoices"), _("Needs action"), _invoice_context("Pending HR Review")),
		_row(_("Invoices"), _("Changes Requested"), 1, _("invoice"), _("Needs action"), _invoice_context("Changes Requested")),
		_row(_("Invoices"), _("Pending Employee Confirmation"), 1, _("invoice"), _("Needs action"), _invoice_context("Pending Employee Confirmation")),
		_row(_("Invoices"), _("Approved for Payment"), 2, _("invoices"), _("Needs action"), _invoice_context("Approved for Payment")),
		_row(_("Invoices"), _("Paid"), 8, _("invoices"), _("Complete"), _invoice_context("Paid")),
	]
	summary = _summary(24, 736, 12, 2)
	chart = _attention_chart(4, 2, 2, 4)
	return rows, summary, chart


def _summary(active_employees, hours, pending_actions, approved_for_payment):
	return [
		{"value": cint(active_employees), "label": _("Active Employees"), "datatype": "Int"},
		{"value": flt(hours, 2), "label": _("Hours Logged"), "datatype": "Float"},
		{
			"value": cint(pending_actions),
			"label": _("Items Needing Action"),
			"datatype": "Int",
			"indicator": "Red" if pending_actions else "Green",
		},
		{
			"value": cint(approved_for_payment),
			"label": _("Invoices Ready for Payment"),
			"datatype": "Int",
			"indicator": "Orange" if approved_for_payment else "Green",
		},
	]


def _attention_chart(timesheets, leaves, expenses, invoices):
	return {
		"data": {
			"labels": [_('Timesheets'), _('Leave'), _('Expenses'), _('Invoices')],
			"datasets": [
				{
					"name": _("Needs action"),
					"values": [cint(timesheets), cint(leaves), cint(expenses), cint(invoices)],
				}
			],
		},
		"type": "bar",
		"colors": ["#D97706"],
	}
