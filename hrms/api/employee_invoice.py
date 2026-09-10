from __future__ import annotations

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, getdate, now_datetime, nowdate


HR_ROLES = {"HR Manager", "HR User", "System Manager"}
EMPLOYEE_EDITABLE_FIELDS = {
	"due_date",
	"period_start",
	"period_end",
	"due_hours",
	"payee_name",
	"payee_address",
	"preferred_payment_method",
	"payment_details",
	"bank_name",
	"bank_account_no",
	"iban",
	"employee_note",
}
ADDITION_TYPES = {"Bonus", "Commission", "Paid Leave Adjustment", "Other"}
DEDUCTION_TYPES = {"Prepayment", "Deduction"}
PAYMENT_METHODS = {"Bank Transfer", "Cash", "Online Payment Service", "Cryptocurrency", "Other"}
INVOICE_LEAVE_TYPES = ("Paid Leave", "Sick Leave", "Unpaid Leave")
LEAVE_HOURS_PER_DAY = 8


def _is_hr(user=None):
	return bool(HR_ROLES.intersection(frappe.get_roles(user or frappe.session.user)))


def _require_hr():
	if not _is_hr():
		frappe.throw(_("Only HR can complete this action."), frappe.PermissionError)


def _can_access_company(user, company):
	if "System Manager" in frappe.get_roles(user) or user == "Administrator":
		return True
	permissions = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Company"},
		fields=["for_value", "applicable_for"],
		limit_page_length=200,
	)
	allowed = [row.for_value for row in permissions if not row.applicable_for or row.applicable_for == "Employee Invoice"]
	return not allowed or company in allowed


def _current_employee():
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user, "status": "Active"},
		[
			"name",
			"employee_name",
			"company",
			"user_id",
			"bank_name",
			"bank_ac_no",
			"iban",
			"custom_invoice_calculation_method",
			"custom_monthly_invoice_amount",
			"custom_invoice_hourly_rate",
			"custom_invoice_payee_name",
			"custom_invoice_payee_address",
			"custom_preferred_payment_method",
			"custom_invoice_payment_details",
			"custom_invoice_currency",
		],
		as_dict=True,
	)
	if not employee:
		frappe.throw(_("No active employee is linked to your user account."), frappe.PermissionError)
	return employee


def _get_doc(name):
	doc = frappe.get_doc("Employee Invoice", name)
	if doc.employee_user == frappe.session.user:
		return doc
	if doc.status == "Draft":
		frappe.throw(_("Employee invoice drafts are private."), frappe.PermissionError)
	if _is_hr() and _can_access_company(frappe.session.user, doc.company):
		return doc
	if _is_hr():
		frappe.throw(_("You do not have access to this company."), frappe.PermissionError)
	else:
		frappe.throw(_("You can only access your own invoices."), frappe.PermissionError)


def employee_invoice_query_conditions(user=None):
	user = user or frappe.session.user
	escaped_user = frappe.db.escape(user)
	if _is_hr(user):
		return f"(`tabEmployee Invoice`.status != 'Draft' OR `tabEmployee Invoice`.employee_user = {escaped_user})"
	return f"`tabEmployee Invoice`.employee_user = {escaped_user}"


def employee_invoice_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if doc.employee_user == user:
		return True
	if ptype in {"read", "print", "email", "export"}:
		return bool(doc.status != "Draft" and _is_hr(user) and _can_access_company(user, doc.company))
	return None


def _persist(doc, insert=False):
	doc.flags.invoice_api_action = True
	if insert:
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return doc


def _configured_employee(employee):
	missing = []
	if not employee.custom_invoice_calculation_method:
		missing.append(_("calculation method"))
	if not employee.custom_invoice_currency:
		missing.append(_("currency"))
	if not employee.custom_invoice_payee_name:
		missing.append(_("legal payee name"))
	if not employee.custom_preferred_payment_method:
		missing.append(_("preferred payment method"))
	if employee.custom_invoice_calculation_method == "Fixed Monthly" and flt(
		employee.custom_monthly_invoice_amount
	) <= 0:
		missing.append(_("monthly amount"))
	if employee.custom_invoice_calculation_method == "Hourly" and flt(
		employee.custom_invoice_hourly_rate
	) <= 0:
		missing.append(_("hourly rate"))
	if missing:
		frappe.throw(
			_("HR must complete these invoice settings in the Employee record: {0}.").format(
				", ".join(missing)
			)
		)
	return employee


def _company_snapshot(company):
	data = frappe.db.get_value("Company", company, ["company_name", "country"], as_dict=True) or {}
	address_name = frappe.db.get_value(
		"Dynamic Link",
		{
			"link_doctype": "Company",
			"link_name": company,
			"parenttype": "Address",
		},
		"parent",
	)
	address = ""
	if address_name:
		address_doc = frappe.get_doc("Address", address_name)
		address = "\n".join(
			filter(
				None,
				[
					address_doc.address_line1,
					address_doc.address_line2,
					", ".join(filter(None, [address_doc.city, address_doc.state, address_doc.pincode])),
					address_doc.country,
				],
			)
		)
	return data.get("company_name") or company, address or data.get("country") or ""


def _timesheet_rows(employee, period_start, period_end):
	rows = frappe.db.sql(
		"""
		SELECT
			t.name AS timesheet,
			t.modified,
			t.docstatus,
			COALESCE(t.custom_is_weekly, 0) AS custom_is_weekly,
			COALESCE(t.custom_weekly_status, '') AS custom_weekly_status,
			DATE(d.from_time) AS work_date,
			SUM(d.hours) AS hours
		FROM `tabTimesheet` t
		INNER JOIN `tabTimesheet Detail` d ON d.parent = t.name
		WHERE t.employee = %(employee)s
		  AND t.docstatus < 2
		  AND DATE(d.from_time) BETWEEN %(period_start)s AND %(period_end)s
		GROUP BY t.name, t.modified, t.docstatus, t.custom_is_weekly,
		         t.custom_weekly_status, DATE(d.from_time)
		ORDER BY work_date, timesheet
		""",
		{"employee": employee, "period_start": period_start, "period_end": period_end},
		as_dict=True,
	)
	result = []
	all_final = True
	for row in rows:
		is_final = (
			row.docstatus == 1 and row.custom_weekly_status == "Closed"
			if cint(row.custom_is_weekly)
			else row.docstatus == 1
		)
		all_final = all_final and is_final
		result.append(
			{
				"timesheet": row.timesheet,
				"work_date": str(row.work_date),
				"hours": flt(row.hours, 2),
				"approval_status": "Finalized" if is_final else "Not finalized",
				"modified": str(row.modified),
			}
		)
	return result, all_final


def _leave_rows(employee, period_start, period_end):
	from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days

	leaves = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"leave_type": ("in", INVOICE_LEAVE_TYPES),
			"status": "Approved",
			"docstatus": 1,
			"from_date": ("<=", period_end),
			"to_date": (">=", period_start),
		},
		fields=[
			"name",
			"leave_type",
			"from_date",
			"to_date",
			"half_day",
			"half_day_date",
			"is_hourly_leave",
			"hourly_start_time",
			"hourly_end_time",
			"modified",
		],
		order_by="from_date asc",
	)
	result = []
	for row in leaves:
		from_date = max(getdate(row.from_date), getdate(period_start))
		to_date = min(getdate(row.to_date), getdate(period_end))
		half_day = cint(row.half_day) and row.half_day_date and from_date <= getdate(row.half_day_date) <= to_date
		days = get_number_of_leave_days(
			employee,
			row.leave_type,
			from_date,
			to_date,
			half_day=cint(half_day),
			half_day_date=row.half_day_date if half_day else None,
			is_hourly_leave=row.is_hourly_leave,
			hourly_start_time=row.hourly_start_time,
			hourly_end_time=row.hourly_end_time,
		)
		hours = flt(flt(days) * LEAVE_HOURS_PER_DAY, 2)
		if hours <= 0:
			continue
		result.append(
			{
				"name": row.name,
				"leave_type": row.leave_type,
				"from_date": str(from_date),
				"to_date": str(to_date),
				"hours": hours,
				"modified": str(row.modified),
			}
		)
	return result


def _leave_totals(rows):
	totals = {leave_type: 0.0 for leave_type in INVOICE_LEAVE_TYPES}
	for row in rows:
		totals[row["leave_type"]] = flt(totals[row["leave_type"]] + row["hours"], 2)
	return totals


def _leave_summary(rows):
	return "\n".join(
		f"{row['leave_type']}: {row['from_date']} to {row['to_date']} ({row['hours']:.2f} hours)"
		for row in rows
	)


def _hash(value):
	return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _calculate_amounts(
	calculation_method,
	worked_hours,
	monthly_amount,
	hourly_rate,
	adjustments,
	due_hours=0,
	paid_leave_hours=0,
	sick_leave_hours=0,
	unpaid_leave_hours=0,
):
	if calculation_method == "Fixed Monthly":
		base_amount = flt(monthly_amount, 2)
		payable_hours = max(flt(due_hours) - flt(unpaid_leave_hours), 0)
		unpaid_leave_deduction = (
			flt(base_amount * min(flt(unpaid_leave_hours) / flt(due_hours), 1), 2)
			if flt(due_hours) > 0
			else 0
		)
	else:
		payable_hours = flt(worked_hours) + flt(paid_leave_hours) + flt(sick_leave_hours)
		base_amount = flt(payable_hours * flt(hourly_rate), 2)
		unpaid_leave_deduction = 0
	additions = deductions = 0
	for row in adjustments:
		if flt(row.quantity) <= 0 or flt(row.unit_amount) < 0 or not row.note:
			frappe.throw(_("Every adjustment needs a positive quantity, a non-negative amount, and a reason."))
		row.amount = flt(row.quantity * row.unit_amount, 2)
		if row.adjustment_type in ADDITION_TYPES and row.adjustment_type != "Other":
			row.effect = "Addition"
			additions += row.amount
		elif row.adjustment_type in DEDUCTION_TYPES:
			row.effect = "Deduction"
			deductions += row.amount
		elif row.adjustment_type == "Other" and row.effect == "Addition":
			additions += row.amount
		elif row.adjustment_type == "Other" and row.effect == "Deduction":
			deductions += row.amount
		else:
			frappe.throw(_("Unsupported adjustment type."))
	return (
		base_amount,
		flt(additions, 2),
		flt(deductions + unpaid_leave_deduction, 2),
		flt(base_amount + additions - deductions - unpaid_leave_deduction, 2),
		flt(payable_hours, 2),
		unpaid_leave_deduction,
	)


def _material_payload(doc):
	return {
		"period_start": str(doc.period_start),
		"period_end": str(doc.period_end),
		"due_date": str(doc.due_date),
		"due_hours": flt(doc.due_hours, 2),
		"worked_hours": flt(doc.worked_hours, 2),
		"paid_leave_hours": flt(doc.paid_leave_hours, 2),
		"sick_leave_hours": flt(doc.sick_leave_hours, 2),
		"unpaid_leave_hours": flt(doc.unpaid_leave_hours, 2),
		"payable_hours": flt(doc.payable_hours, 2),
		"unpaid_leave_deduction": flt(doc.unpaid_leave_deduction, 2),
		"calculation_method": doc.calculation_method,
		"monthly_amount": flt(doc.monthly_amount, 2),
		"hourly_rate": flt(doc.hourly_rate, 2),
		"base_amount": flt(doc.base_amount, 2),
		"currency": doc.currency,
		"payee_name": doc.payee_name,
		"payee_address": doc.payee_address,
		"preferred_payment_method": doc.preferred_payment_method,
		"payment_details": doc.payment_details,
		"bank_name": doc.bank_name,
		"bank_account_no": doc.bank_account_no,
		"iban": doc.iban,
		"adjustments": [
			{
				"type": row.adjustment_type,
				"effect": row.effect,
				"quantity": flt(row.quantity, 4),
				"unit_amount": flt(row.unit_amount, 2),
				"amount": flt(row.amount, 2),
				"note": row.note,
			}
			for row in doc.adjustments
		],
		"grand_total": flt(doc.grand_total, 2),
		"time_source_hash": doc.time_source_hash,
		"leave_source_hash": doc.leave_source_hash,
	}


def _recalculate(doc):
	rows, all_final = _timesheet_rows(doc.employee, doc.period_start, doc.period_end)
	doc.set("time_summary", [])
	for row in rows:
		doc.append("time_summary", {key: row[key] for key in ("timesheet", "work_date", "hours", "approval_status")})
	doc.worked_hours = flt(sum(row["hours"] for row in rows), 2)
	doc.time_approval_ready = cint(all_final)
	doc.time_source_hash = _hash(rows)
	leave_rows = _leave_rows(doc.employee, doc.period_start, doc.period_end)
	leave_totals = _leave_totals(leave_rows)
	doc.paid_leave_hours = leave_totals["Paid Leave"]
	doc.sick_leave_hours = leave_totals["Sick Leave"]
	doc.unpaid_leave_hours = leave_totals["Unpaid Leave"]
	doc.leave_source_hash = _hash(leave_rows)
	doc.leave_summary = _leave_summary(leave_rows)

	(
		doc.base_amount,
		doc.total_additions,
		doc.total_deductions,
		doc.grand_total,
		doc.payable_hours,
		doc.unpaid_leave_deduction,
	) = _calculate_amounts(
		doc.calculation_method,
		doc.worked_hours,
		doc.monthly_amount,
		doc.hourly_rate,
		doc.adjustments,
		doc.due_hours,
		doc.paid_leave_hours,
		doc.sick_leave_hours,
		doc.unpaid_leave_hours,
	)
	return doc


def _validate_leave_calculation(doc):
	if (
		doc.calculation_method == "Fixed Monthly"
		and flt(doc.unpaid_leave_hours) > 0
		and flt(doc.due_hours) <= 0
	):
		frappe.throw(_("Due hours are required when approved unpaid leave affects a fixed monthly invoice."))


def _serialize(doc):
	return {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"company": doc.company,
		"status": doc.status,
		"currency": doc.currency,
		"invoice_date": str(doc.invoice_date),
		"due_date": str(doc.due_date),
		"period_start": str(doc.period_start),
		"period_end": str(doc.period_end),
		"due_hours": flt(doc.due_hours, 2),
		"worked_hours": flt(doc.worked_hours, 2),
		"paid_leave_hours": flt(doc.paid_leave_hours, 2),
		"sick_leave_hours": flt(doc.sick_leave_hours, 2),
		"unpaid_leave_hours": flt(doc.unpaid_leave_hours, 2),
		"payable_hours": flt(doc.payable_hours, 2),
		"unpaid_leave_deduction": flt(doc.unpaid_leave_deduction, 2),
		"time_approval_ready": cint(doc.time_approval_ready),
		"calculation_method": doc.calculation_method,
		"monthly_amount": flt(doc.monthly_amount, 2),
		"hourly_rate": flt(doc.hourly_rate, 2),
		"base_amount": flt(doc.base_amount, 2),
		"total_additions": flt(doc.total_additions, 2),
		"total_deductions": flt(doc.total_deductions, 2),
		"grand_total": flt(doc.grand_total, 2),
		"payee_name": doc.payee_name,
		"payee_address": doc.payee_address,
		"preferred_payment_method": doc.preferred_payment_method,
		"payment_details": doc.payment_details,
		"bank_name": doc.bank_name,
		"bank_account_no": doc.bank_account_no,
		"iban": doc.iban,
		"bill_to_name": doc.bill_to_name,
		"bill_to_address": doc.bill_to_address,
		"employee_note": doc.employee_note,
		"hr_note": doc.hr_note,
		"return_reason": doc.return_reason,
		"employee_confirmed_at": str(doc.employee_confirmed_at) if doc.employee_confirmed_at else None,
		"hr_approved_at": str(doc.hr_approved_at) if doc.hr_approved_at else None,
		"payment_date": str(doc.payment_date) if doc.payment_date else None,
		"payment_reference": doc.payment_reference,
		"actual_payment_method": doc.actual_payment_method,
		"leave_summary": doc.leave_summary,
		"time_summary": [
			{"date": str(row.work_date), "timesheet": row.timesheet, "hours": flt(row.hours, 2), "status": row.approval_status}
			for row in doc.time_summary
		],
		"adjustments": [
			{"adjustment_type": row.adjustment_type, "effect": row.effect, "quantity": flt(row.quantity, 4), "unit_amount": flt(row.unit_amount, 2), "amount": flt(row.amount, 2), "note": row.note}
			for row in doc.adjustments
		],
		"is_hr": _is_hr(),
		"is_employee_owner": doc.employee_user == frappe.session.user,
		"can_employee_edit": doc.employee_user == frappe.session.user and doc.status in {"Draft", "Changes Requested"},
	}


def _hr_users(company=None):
	users = set()
	for role in ("HR Manager", "HR User"):
		users.update(
			frappe.get_all(
				"Has Role",
				filters={"role": role, "parenttype": "User"},
				pluck="parent",
				limit_page_length=200,
			)
		)
	return [
		user
		for user in users
		if frappe.db.get_value("User", user, "enabled")
		and (not company or _can_access_company(user, company))
	]


def _notify(users, doc, message):
	for user in set(filter(None, users)):
		if user == frappe.session.user:
			continue
		notification = frappe.new_doc("PWA Notification")
		notification.from_user = frappe.session.user
		notification.to_user = user
		notification.message = message
		notification.reference_document_type = "Employee Invoice"
		notification.reference_document_name = doc.name
		notification.insert(ignore_permissions=True)


def _queue_email(doc, kind):
	frappe.enqueue(
		"hrms.api.employee_invoice.send_invoice_email",
		queue="short",
		enqueue_after_commit=True,
		invoice=doc.name,
		kind=kind,
	)


def send_invoice_email(invoice, kind):
	doc = frappe.get_doc("Employee Invoice", invoice)
	if kind == "review":
		recipients = _hr_users(doc.company)
		subject = _("Invoice {0} is ready for HR review").format(doc.name)
	else:
		recipients = list(set(_hr_users(doc.company) + [doc.employee_user]))
		subject = _("Invoice {0} has been paid").format(doc.name)
	if not recipients:
		return
	try:
		pdf = frappe.get_print("Employee Invoice", doc.name, print_format="Employee Invoice", as_pdf=True)
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=_("The invoice is attached."),
			attachments=[{"fname": f"{doc.name}.pdf", "fcontent": pdf}],
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Employee Invoice email failed: {doc.name}")


@frappe.whitelist()
def get_my_invoices():
	employee = _current_employee()
	return frappe.get_list(
		"Employee Invoice",
		filters={"employee": employee.name},
		fields=["name", "status", "period_start", "period_end", "due_date", "worked_hours", "grand_total", "currency", "modified"],
		order_by="modified desc",
		limit_page_length=100,
	)


@frappe.whitelist()
def get_hr_invoice_queue():
	_require_hr()
	return frappe.get_list(
		"Employee Invoice",
		filters={"status": ("not in", ["Draft", "Cancelled"])},
		fields=["name", "employee_name", "company", "status", "period_start", "period_end", "grand_total", "currency", "modified"],
		order_by="modified desc",
		limit_page_length=200,
	)


@frappe.whitelist()
def get_employee_invoice(name):
	return _serialize(_get_doc(name))


@frappe.whitelist(methods=["POST"])
def create_employee_invoice(due_date):
	employee = _configured_employee(_current_employee())
	due = getdate(due_date)
	period_start = add_months(due, -1)
	bill_to_name, bill_to_address = _company_snapshot(employee.company)
	doc = frappe.new_doc("Employee Invoice")
	doc.update(
		{
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"employee_user": employee.user_id,
			"company": employee.company,
			"status": "Draft",
			"invoice_date": nowdate(),
			"due_date": due,
			"period_start": period_start,
			"period_end": due,
			"calculation_method": employee.custom_invoice_calculation_method,
			"monthly_amount": employee.custom_monthly_invoice_amount,
			"hourly_rate": employee.custom_invoice_hourly_rate,
			"currency": employee.custom_invoice_currency,
			"payee_name": employee.custom_invoice_payee_name,
			"payee_address": employee.custom_invoice_payee_address,
			"preferred_payment_method": employee.custom_preferred_payment_method,
			"payment_details": employee.custom_invoice_payment_details,
			"bank_name": employee.bank_name,
			"bank_account_no": employee.bank_ac_no,
			"iban": employee.iban,
			"bill_to_name": bill_to_name,
			"bill_to_address": bill_to_address,
		}
	)
	_recalculate(doc)
	_persist(doc, insert=True)
	return _serialize(doc)


@frappe.whitelist(methods=["POST"])
def save_employee_invoice(name, values=None):
	doc = _get_doc(name)
	if doc.employee_user != frappe.session.user or doc.status not in {"Draft", "Changes Requested"}:
		frappe.throw(_("This invoice is not editable by the employee."), frappe.PermissionError)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	for field in EMPLOYEE_EDITABLE_FIELDS:
		if field in values:
			setattr(doc, field, values[field])
	_recalculate(doc)
	_persist(doc)
	return _serialize(doc)


@frappe.whitelist(methods=["POST"])
def confirm_employee_invoice(name):
	doc = _get_doc(name)
	if doc.employee_user != frappe.session.user or doc.status not in {"Draft", "Changes Requested", "Pending Employee Confirmation"}:
		frappe.throw(_("This invoice cannot be confirmed."), frappe.PermissionError)
	_recalculate(doc)
	_validate_leave_calculation(doc)
	doc.status = "Pending HR Review"
	doc.return_reason = None
	doc.employee_confirmed_at = now_datetime()
	doc.employee_confirmed_by = frappe.session.user
	doc.employee_confirmation_hash = _hash(_material_payload(doc))
	_persist(doc)
	_notify(_hr_users(doc.company), doc, _("Invoice {0} is ready for HR review.").format(frappe.bold(doc.name)))
	_queue_email(doc, "review")
	return _serialize(doc)


@frappe.whitelist(methods=["POST"])
def hr_update_employee_invoice(name, values=None, reason=None):
	_require_hr()
	if not reason:
		frappe.throw(_("A reason is required for HR changes."))
	doc = _get_doc(name)
	if doc.status in {"Approved for Payment", "Paid", "Cancelled"}:
		frappe.throw(_("This invoice can no longer be edited."))
	before_hash = _hash(_material_payload(doc))
	previous_status = doc.status
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	for field in EMPLOYEE_EDITABLE_FIELDS | {"monthly_amount", "hourly_rate", "currency", "hr_note"}:
		if field in values:
			setattr(doc, field, values[field])
	if "adjustments" in values:
		doc.set("adjustments", [])
		for row in values["adjustments"] or []:
			doc.append("adjustments", row)
	_recalculate(doc)
	doc.last_change_reason = reason
	material_changed = before_hash != _hash(_material_payload(doc))
	if material_changed:
		doc.status = "Pending Employee Confirmation"
		doc.employee_confirmation_hash = None
	else:
		doc.status = previous_status
	_persist(doc)
	if material_changed:
		_notify([doc.employee_user], doc, _("HR updated invoice {0}; your confirmation is required.").format(frappe.bold(doc.name)))
	return _serialize(doc)


@frappe.whitelist(methods=["POST"])
def hr_return_employee_invoice(name, reason):
	_require_hr()
	if not reason:
		frappe.throw(_("A return reason is required."))
	doc = _get_doc(name)
	if doc.status not in {"Pending HR Review", "Pending Employee Confirmation"}:
		frappe.throw(_("This invoice cannot be returned."))
	doc.status = "Changes Requested"
	doc.return_reason = reason
	doc.employee_confirmation_hash = None
	_persist(doc)
	_notify([doc.employee_user], doc, _("Invoice {0} was returned: {1}").format(frappe.bold(doc.name), reason))
	return _serialize(doc)


@frappe.whitelist(methods=["POST"])
def hr_approve_employee_invoice(name):
	_require_hr()
	doc = _get_doc(name)
	if doc.status != "Pending HR Review":
		frappe.throw(_("The invoice is not ready for HR approval."))
	old_time_hash = doc.time_source_hash
	_recalculate(doc)
	current_hash = _hash(_material_payload(doc))
	if old_time_hash != doc.time_source_hash or current_hash != doc.employee_confirmation_hash:
		doc.status = "Pending Employee Confirmation"
		doc.employee_confirmation_hash = None
		doc.last_change_reason = _("Timesheet or invoice data changed after employee confirmation.")
		_persist(doc)
		_notify([doc.employee_user], doc, _("Invoice {0} changed and needs your confirmation again.").format(frappe.bold(doc.name)))
		return {"needs_employee_confirmation": True, "invoice": _serialize(doc)}
	if not cint(doc.time_approval_ready):
		frappe.throw(_("All referenced timesheets must be finalized before approval."))
	doc.status = "Approved for Payment"
	doc.hr_approved_at = now_datetime()
	doc.hr_approved_by = frappe.session.user
	_persist(doc)
	_notify([doc.employee_user], doc, _("Invoice {0} was approved for payment.").format(frappe.bold(doc.name)))
	return {"needs_employee_confirmation": False, "invoice": _serialize(doc)}


@frappe.whitelist(methods=["POST"])
def mark_employee_invoice_paid(name, payment_date, payment_reference, payment_method=None):
	_require_hr()
	if not payment_date or not payment_reference or not payment_method:
		frappe.throw(_("Payment method, date, and reference are required."))
	if payment_method not in PAYMENT_METHODS:
		frappe.throw(_("Unsupported payment method."))
	doc = _get_doc(name)
	if doc.status != "Approved for Payment":
		frappe.throw(_("Only an approved invoice can be marked paid."))
	doc.status = "Paid"
	doc.actual_payment_method = payment_method
	doc.payment_date = payment_date
	doc.payment_reference = payment_reference
	doc.paid_at = now_datetime()
	doc.paid_by = frappe.session.user
	doc.flags.ignore_paid_protection = True
	_persist(doc)
	_notify([doc.employee_user], doc, _("Invoice {0} was marked paid.").format(frappe.bold(doc.name)))
	_queue_email(doc, "paid")
	return _serialize(doc)
