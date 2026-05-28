import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.model.workflow import get_workflow_name
from frappe.query_builder import Order
from frappe.utils import add_days, date_diff, getdate, strip_html

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

SUPPORTED_FIELD_TYPES = [
	"Link",
	"Select",
	"Small Text",
	"Text",
	"Long Text",
	"Text Editor",
	"Table",
	"Check",
	"Data",
	"Float",
	"Int",
	"Section Break",
	"Date",
	"Time",
	"Datetime",
	"Currency",
]


@frappe.whitelist()
def get_current_user_info() -> dict:
	current_user = frappe.session.user
	user = frappe.db.get_value(
		"User", current_user, ["name", "first_name", "full_name", "user_image"], as_dict=True
	)
	user["roles"] = frappe.get_roles(current_user)

	return user


@frappe.whitelist()
def get_current_employee_info() -> dict:
	current_user = frappe.session.user
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": current_user, "status": "Active"},
		[
			"name",
			"first_name",
			"employee_name",
			"designation",
			"department",
			"company",
			"reports_to",
			"user_id",
		],
		as_dict=True,
	)
	return employee


@frappe.whitelist()
def get_all_employees() -> list[dict]:
	return frappe.get_list(
		"Employee",
		fields=[
			"name",
			"employee_name",
			"designation",
			"department",
			"company",
			"reports_to",
			"user_id",
			"image",
			"status",
		],
		limit=999999,
	)


def get_current_employee() -> str:
	employee = get_current_employee_info().get("name")
	if not employee:
		frappe.throw(_("Employee not found"), frappe.PermissionError)
	return employee


# HR Settings
@frappe.whitelist()
def get_hr_settings() -> dict:
	settings = frappe.db.get_singles_dict("HR Settings", cast=True)
	return frappe._dict(
		allow_employee_checkin_from_mobile_app=settings.allow_employee_checkin_from_mobile_app,
		allow_geolocation_tracking=settings.allow_geolocation_tracking,
		prevent_self_leave_approval=settings.prevent_self_leave_approval,
	)


# Notifications
@frappe.whitelist()
def get_unread_notifications_count() -> int:
	return frappe.db.count(
		"PWA Notification",
		{"to_user": frappe.session.user, "read": 0},
	)


@frappe.whitelist()
def mark_all_notifications_as_read() -> None:
	frappe.db.set_value(
		"PWA Notification",
		{"to_user": frappe.session.user, "read": 0},
		"read",
		1,
		update_modified=False,
	)


@frappe.whitelist()
def are_push_notifications_enabled() -> bool:
	try:
		return frappe.db.get_single_value("Push Notification Settings", "enable_push_notification_relay")
	except frappe.DoesNotExistError:
		# push notifications are not supported in the current framework version
		return False


# Attendance
@frappe.whitelist()
def get_attendance_calendar_events(from_date: str, to_date: str) -> dict[str, str]:
	employee = get_current_employee()
	holidays = get_holidays_for_calendar(employee, from_date, to_date)
	attendance = get_attendance_for_calendar(employee, from_date, to_date)
	events = {}

	date = getdate(from_date)
	while date_diff(to_date, date) >= 0:
		date_str = date.strftime("%Y-%m-%d")
		if date in attendance:
			events[date_str] = attendance[date]
		elif date in holidays:
			events[date_str] = "Holiday"
		date = add_days(date, 1)

	return events


def get_attendance_for_calendar(employee: str, from_date: str, to_date: str) -> list[dict[str, str]]:
	attendance = frappe.get_all(
		"Attendance",
		{"employee": employee, "attendance_date": ["between", [from_date, to_date]], "docstatus": 1},
		["attendance_date", "status"],
	)
	return {d["attendance_date"]: d["status"] for d in attendance}


def get_holidays_for_calendar(employee: str, from_date: str, to_date: str) -> list[str]:
	if holiday_list := get_holiday_list_for_employee(employee, raise_exception=False):
		return frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "holiday_date": ["between", [from_date, to_date]]},
			pluck="holiday_date",
		)

	return []


@frappe.whitelist()
def get_shift_requests(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
) -> list[dict]:
	filters = get_filters("Shift Request", employee, approver_id, for_approval)
	fields = [
		"name",
		"employee",
		"employee_name",
		"shift_type",
		"from_date",
		"to_date",
		"status",
		"approver",
		"docstatus",
		"creation",
	]

	if workflow_state_field := get_workflow_state_field("Shift Request"):
		fields.append(workflow_state_field)

	shift_requests = frappe.get_list(
		"Shift Request",
		fields=fields,
		filters=filters,
		order_by="creation desc",
		limit=limit,
	)

	if workflow_state_field:
		for application in shift_requests:
			application["workflow_state_field"] = workflow_state_field

	return shift_requests


@frappe.whitelist()
def get_attendance_requests(
	employee: str,
	for_approval: bool = False,
	limit: int | None = None,
) -> list[dict]:
	filters = get_filters("Attendance Request", employee, None, for_approval)
	fields = [
		"name",
		"reason",
		"employee",
		"employee_name",
		"from_date",
		"to_date",
		"include_holidays",
		"shift",
		"docstatus",
		"creation",
	]

	if workflow_state_field := get_workflow_state_field("Attendance Request"):
		fields.append(workflow_state_field)

	attendance_requests = frappe.get_list(
		"Attendance Request",
		fields=fields,
		filters=filters,
		order_by="creation desc",
		limit=limit,
	)

	if workflow_state_field:
		for application in attendance_requests:
			application["workflow_state_field"] = workflow_state_field

	return attendance_requests


def get_filters(
	doctype: str,
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
) -> dict:
	filters = frappe._dict()
	if for_approval:
		filters.docstatus = 0
		filters.employee = ("!=", employee)

		if workflow := get_workflow(doctype):
			allowed_states = get_allowed_states_for_workflow(workflow, approver_id)
			filters[workflow.workflow_state_field] = ("in", allowed_states)
		elif doctype != "Attendance Request":
			approver_field_map = {
				"Shift Request": "approver",
				"Leave Application": "leave_approver",
				"Expense Claim": "expense_approver",
			}
			filters.status = "Open" if doctype == "Leave Application" else "Draft"
			if approver_id:
				filters[approver_field_map[doctype]] = approver_id
	else:
		filters.docstatus = ("!=", 2)
		filters.employee = employee

	return filters


@frappe.whitelist()
def get_shift_request_approvers(employee: str) -> str | list[str]:
	shift_request_approver, department = frappe.get_cached_value(
		"Employee",
		employee,
		["shift_request_approver", "department"],
	)

	department_approvers = []
	if department:
		department_approvers = get_department_approvers(department, "shift_request_approver")
		if not shift_request_approver:
			shift_request_approver = frappe.db.get_value(
				"Department Approver",
				{"parent": department, "parentfield": "shift_request_approver", "idx": 1},
				"approver",
			)

	shift_request_approver_name = frappe.db.get_value("User", shift_request_approver, "full_name", cache=True)

	if shift_request_approver and shift_request_approver not in [
		approver.name for approver in department_approvers
	]:
		department_approvers.insert(
			0, {"name": shift_request_approver, "full_name": shift_request_approver_name}
		)

	return department_approvers


@frappe.whitelist()
def get_shifts() -> list[dict[str, str]]:
	employee = get_current_employee()
	ShiftAssignment = frappe.qb.DocType("Shift Assignment")
	ShiftType = frappe.qb.DocType("Shift Type")
	return (
		frappe.qb.from_(ShiftAssignment)
		.join(ShiftType)
		.on(ShiftAssignment.shift_type == ShiftType.name)
		.select(
			ShiftAssignment.name,
			ShiftAssignment.shift_type,
			ShiftAssignment.start_date,
			ShiftAssignment.end_date,
			ShiftType.start_time,
			ShiftType.end_time,
		)
		.where(
			(ShiftAssignment.employee == employee)
			& (ShiftAssignment.status == "Active")
			& (ShiftAssignment.docstatus == 1)
		)
		.orderby(ShiftAssignment.start_date, order=Order.asc)
	).run(as_dict=True)


# Leaves and Holidays
@frappe.whitelist()
def get_leave_applications(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
) -> list[dict]:
	filters = get_filters("Leave Application", employee, approver_id, for_approval)
	fields = [
		"name",
		"posting_date",
		"employee",
		"employee_name",
		"leave_type",
		"status",
		"from_date",
		"to_date",
		"half_day",
		"half_day_date",
		"description",
		"total_leave_days",
		"leave_balance",
		"leave_approver",
		"posting_date",
		"creation",
	]

	if workflow_state_field := get_workflow_state_field("Leave Application"):
		fields.append(workflow_state_field)

	applications = frappe.get_list(
		"Leave Application",
		fields=fields,
		filters=filters,
		order_by="posting_date desc",
		limit=limit,
	)

	if workflow_state_field:
		for application in applications:
			application["workflow_state_field"] = workflow_state_field

	return applications


@frappe.whitelist()
def get_leave_balance_map() -> dict[str, dict[str, float]]:
	"""
	Returns a map of leave type and balance details like:
	{
	        'Casual Leave': {'allocated_leaves': 10.0, 'balance_leaves': 5.0},
	        'Earned Leave': {'allocated_leaves': 3.0, 'balance_leaves': 3.0},
	}
	"""
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	employee = get_current_employee()

	date = getdate()
	leave_map = {}

	leave_details = get_leave_details(employee, date)
	allocation = leave_details["leave_allocation"]

	for leave_type, details in allocation.items():
		leave_map[leave_type] = {
			"allocated_leaves": details.get("total_leaves"),
			"balance_leaves": details.get("remaining_leaves"),
		}

	return leave_map


@frappe.whitelist()
def get_holidays_for_employee(employee: str) -> list[dict]:
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return []

	Holiday = frappe.qb.DocType("Holiday")
	holidays = (
		frappe.qb.from_(Holiday)
		.select(Holiday.name, Holiday.holiday_date, Holiday.description)
		.where((Holiday.parent == holiday_list) & (Holiday.weekly_off == 0))
		.orderby(Holiday.holiday_date, order=Order.asc)
	).run(as_dict=True)

	for holiday in holidays:
		holiday["description"] = strip_html(holiday["description"] or "").strip()

	return holidays


@frappe.whitelist()
def get_leave_approval_details(employee: str) -> dict:
	leave_approver, department = frappe.get_cached_value(
		"Employee",
		employee,
		["leave_approver", "department"],
	)

	if not leave_approver and department:
		leave_approver = frappe.db.get_value(
			"Department Approver",
			{"parent": department, "parentfield": "leave_approvers", "idx": 1},
			"approver",
		)

	leave_approver_name = frappe.db.get_value("User", leave_approver, "full_name", cache=True)
	department_approvers = get_department_approvers(department, "leave_approvers")

	if leave_approver and leave_approver not in [approver.name for approver in department_approvers]:
		department_approvers.append({"name": leave_approver, "full_name": leave_approver_name})

	return dict(
		leave_approver=leave_approver,
		leave_approver_name=leave_approver_name,
		department_approvers=department_approvers,
		is_mandatory=frappe.db.get_single_value(
			"HR Settings", "leave_approver_mandatory_in_leave_application"
		),
	)


def get_department_approvers(department: str, parentfield: str) -> list[str]:
	if not department:
		return []

	department_details = frappe.db.get_value("Department", department, ["lft", "rgt"], as_dict=True)
	departments = frappe.get_all(
		"Department",
		filters={
			"lft": ("<=", department_details.lft),
			"rgt": (">=", department_details.rgt),
			"disabled": 0,
		},
		pluck="name",
	)

	Approver = frappe.qb.DocType("Department Approver")
	User = frappe.qb.DocType("User")
	department_approvers = (
		frappe.qb.from_(User)
		.join(Approver)
		.on(Approver.approver == User.name)
		.select(User.name.as_("name"), User.full_name.as_("full_name"))
		.where((Approver.parent.isin(departments)) & (Approver.parentfield == parentfield))
	).run(as_dict=True)

	return department_approvers


@frappe.whitelist()
def get_leave_types(employee: str, date: str) -> list:
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	date = date or getdate()

	leave_details = get_leave_details(employee, date)
	leave_types = list(leave_details["leave_allocation"].keys()) + leave_details["lwps"]

	return leave_types


# Expense Claims
@frappe.whitelist()
def get_expense_claims(
	employee: str,
	approver_id: str | None = None,
	for_approval: bool = False,
	limit: int | None = None,
) -> list[dict]:
	filters = get_filters("Expense Claim", employee, approver_id, for_approval)
	fields = [
		"`tabExpense Claim`.name",
		"`tabExpense Claim`.posting_date",
		"`tabExpense Claim`.employee",
		"`tabExpense Claim`.employee_name",
		"`tabExpense Claim`.currency",
		"`tabExpense Claim`.approval_status",
		"`tabExpense Claim`.status",
		"`tabExpense Claim`.expense_approver",
		"`tabExpense Claim`.total_claimed_amount",
		"`tabExpense Claim`.posting_date",
		"`tabExpense Claim`.company",
		"`tabExpense Claim`.creation",
		"`tabExpense Claim Detail`.expense_type",
		{"COUNT": "`tabExpense Claim Detail`.expense_type", "as": "total_expenses"},
	]

	if workflow_state_field := get_workflow_state_field("Expense Claim"):
		fields.append(workflow_state_field)

	claims = frappe.get_list(
		"Expense Claim",
		fields=fields,
		filters=filters,
		order_by="`tabExpense Claim`.posting_date desc",
		group_by="`tabExpense Claim`.name",
		limit=limit,
	)

	if workflow_state_field:
		for claim in claims:
			claim["workflow_state_field"] = workflow_state_field

	return claims


@frappe.whitelist()
def get_expense_claim_summary() -> dict:
	employee = get_current_employee()

	from frappe.query_builder.functions import Sum

	Claim = frappe.qb.DocType("Expense Claim")

	pending_claims_case = (
		frappe.qb.terms.Case().when(Claim.approval_status == "Draft", Claim.total_claimed_amount).else_(0)
	)
	sum_pending_claims = Sum(pending_claims_case).as_("total_pending_amount")

	approved_claims_case = (
		frappe.qb.terms.Case()
		.when(Claim.approval_status == "Approved", Claim.total_sanctioned_amount)
		.else_(0)
	)
	sum_approved_claims = Sum(approved_claims_case).as_("total_approved_amount")

	approved_total_claimed_case = (
		frappe.qb.terms.Case().when(Claim.approval_status == "Approved", Claim.total_claimed_amount).else_(0)
	)
	sum_approved_total_claimed = Sum(approved_total_claimed_case).as_("total_claimed_in_approved")

	rejected_claims_case = (
		frappe.qb.terms.Case().when(Claim.approval_status == "Rejected", Claim.total_claimed_amount).else_(0)
	)
	sum_rejected_claims = Sum(rejected_claims_case).as_("total_rejected_amount")

	summary = (
		frappe.qb.from_(Claim)
		.select(
			sum_pending_claims,
			sum_approved_claims,
			sum_rejected_claims,
			sum_approved_total_claimed,
			Claim.company,
		)
		.where((Claim.docstatus != 2) & (Claim.employee == employee))
	).run(as_dict=True)[0]

	currency = frappe.db.get_value("Company", summary.company, "default_currency")
	summary["currency"] = currency

	return summary


@frappe.whitelist()
def get_expense_type_description(expense_type: str) -> str:
	return frappe.db.get_value("Expense Claim Type", expense_type, "description")


@frappe.whitelist()
def get_expense_claim_types() -> list[dict]:
	ClaimType = frappe.qb.DocType("Expense Claim Type")

	return (frappe.qb.from_(ClaimType).select(ClaimType.name, ClaimType.description)).run(as_dict=True)


@frappe.whitelist()
def get_expense_approval_details(employee: str) -> dict:
	expense_approver, department = frappe.get_cached_value(
		"Employee",
		employee,
		["expense_approver", "department"],
	)

	if not expense_approver and department:
		expense_approver = frappe.db.get_value(
			"Department Approver",
			{"parent": department, "parentfield": "expense_approvers", "idx": 1},
			"approver",
		)

	expense_approver_name = frappe.db.get_value("User", expense_approver, "full_name", cache=True)
	department_approvers = get_department_approvers(department, "expense_approvers")

	if expense_approver and expense_approver not in [approver.name for approver in department_approvers]:
		department_approvers.append({"name": expense_approver, "full_name": expense_approver_name})

	return dict(
		expense_approver=expense_approver,
		expense_approver_name=expense_approver_name,
		department_approvers=department_approvers,
		is_mandatory=frappe.db.get_single_value("HR Settings", "expense_approver_mandatory_in_expense_claim"),
	)


# Employee Advance
@frappe.whitelist()
def get_employee_advance_balance() -> list[dict]:
	employee = get_current_employee()
	Advance = frappe.qb.DocType("Employee Advance")

	advances = (
		frappe.qb.from_(Advance)
		.select(
			Advance.name,
			Advance.employee,
			Advance.status,
			Advance.purpose,
			Advance.paid_amount,
			(Advance.paid_amount - (Advance.claimed_amount + Advance.return_amount)).as_("balance_amount"),
			Advance.posting_date,
			Advance.currency,
		)
		.where(
			(Advance.docstatus == 1)
			& (Advance.paid_amount)
			& (Advance.employee == employee)
			# don't need claimed & returned advances, only partly or completely paid ones
			& (Advance.status.isin(["Paid", "Unpaid"]))
		)
		.orderby(Advance.posting_date, order=Order.desc)
	).run(as_dict=True)

	return advances


# Company
@frappe.whitelist()
def get_company_currencies() -> dict:
	Company = frappe.qb.DocType("Company")
	Currency = frappe.qb.DocType("Currency")

	query = (
		frappe.qb.from_(Company)
		.join(Currency)
		.on(Company.default_currency == Currency.name)
		.select(
			Company.name,
			Company.default_currency,
			Currency.name.as_("currency"),
			Currency.symbol.as_("symbol"),
		)
	)

	companies = query.run(as_dict=True)
	return {company.name: (company.default_currency, company.symbol) for company in companies}


@frappe.whitelist()
def get_currency_symbols() -> dict:
	Currency = frappe.qb.DocType("Currency")

	currencies = (frappe.qb.from_(Currency).select(Currency.name, Currency.symbol)).run(as_dict=True)

	return {currency.name: currency.symbol or currency.name for currency in currencies}


@frappe.whitelist()
def get_company_cost_center_and_expense_account(company: str) -> dict:
	return frappe.db.get_value(
		"Company", company, ["cost_center", "default_expense_claim_payable_account"], as_dict=True
	)


# Form View APIs
@frappe.whitelist()
def get_doctype_fields(doctype: str) -> list[dict]:
	fields = frappe.get_meta(doctype).fields
	return [
		field
		for field in fields
		if field.fieldtype in SUPPORTED_FIELD_TYPES and field.fieldname != "amended_from"
	]


@frappe.whitelist()
def get_doctype_states(doctype: str) -> dict:
	states = frappe.get_meta(doctype).states
	return {state.title: state.color.lower() for state in states}


# File
@frappe.whitelist()
def get_attachments(dt: str, dn: str):
	return frappe.get_list(
		"File",
		fields=["name", "file_name", "file_url", "is_private"],
		filters={"attached_to_name": str(dn), "attached_to_doctype": dt},
	)


@frappe.whitelist()
def upload_base64_file(
	content: str, filename: str, dt: str | None = None, dn: str | None = None, fieldname: str | None = None
):
	import base64
	import io
	from mimetypes import guess_type

	from PIL import Image, ImageOps

	from frappe.handler import ALLOWED_MIMETYPES

	decoded_content = base64.b64decode(content)
	content_type = guess_type(filename)[0]
	if content_type not in ALLOWED_MIMETYPES:
		frappe.throw(_("You can only upload JPG, PNG, PDF, TXT or Microsoft documents."))

	if content_type.startswith("image/jpeg"):
		# transpose the image according to the orientation tag, and remove the orientation data
		with Image.open(io.BytesIO(decoded_content)) as image:
			transpose_img = ImageOps.exif_transpose(image)
			# convert the image back to bytes
			file_content = io.BytesIO()
			transpose_img.save(file_content, format="JPEG")
			file_content = file_content.getvalue()
	else:
		file_content = decoded_content

	return frappe.get_doc(
		{
			"doctype": "File",
			"attached_to_doctype": dt,
			"attached_to_name": dn,
			"attached_to_field": fieldname,
			"folder": "Home",
			"file_name": filename,
			"content": file_content,
			"is_private": 1,
		}
	).insert()


@frappe.whitelist()
def delete_attachment(filename: str):
	frappe.delete_doc("File", filename)


@frappe.whitelist()
def _download_pdf(doctype: str, docname: str) -> str:
	import base64

	from frappe.utils.print_format import download_pdf

	default_print_format = frappe.get_meta(doctype).default_print_format or "Standard"

	try:
		download_pdf(doctype, docname, format=default_print_format)
	except Exception as e:
		frappe.throw(_("Failed to download PDF: {0}").format(str(e)))

	base64content = base64.b64encode(frappe.local.response.filecontent)
	content_type = frappe.local.response.type

	return f"data:{content_type};base64," + base64content.decode("utf-8")


# Workflow
@frappe.whitelist()
def get_workflow(doctype: str) -> dict:
	workflow = get_workflow_name(doctype)
	if not workflow:
		return frappe._dict()
	return frappe.get_doc("Workflow", workflow)


def get_workflow_state_field(doctype: str) -> str | None:
	workflow_name = get_workflow_name(doctype)
	if not workflow_name:
		return None

	override_status, workflow_state_field = frappe.db.get_value(
		"Workflow",
		workflow_name,
		["override_status", "workflow_state_field"],
	)
	# NOTE: checkbox labelled 'Don't Override Status' is named override_status hence the inverted logic
	if not override_status:
		return workflow_state_field
	return None


def get_allowed_states_for_workflow(workflow: dict, user_id: str) -> list[str]:
	user_roles = frappe.get_roles(user_id)
	return [transition.state for transition in workflow.transitions if transition.allowed in user_roles]


# Permissions
@frappe.whitelist()
def get_permitted_fields_for_write(doctype: str) -> list[str]:
	return get_permitted_fields(doctype, permission_type="write")


# Timer
@frappe.whitelist()
def save_timer_log(
	employee: str,
	from_time: str,
	to_time: str,
	hours: float,
	activity_type: str = None,
	project: str = None,
	description: str = None,
) -> str:
	"""
	Appends a timer-captured log to the employee's draft Timesheet for the day.
	Creates a new draft Timesheet if none exists yet. Returns the Timesheet name.
	"""
	from frappe.utils import get_date_str

	hours = float(hours)
	log_date = get_date_str(from_time)

	log_entry = {
		"doctype": "Timesheet Detail",
		"activity_type": activity_type or None,
		"from_time": from_time,
		"to_time": to_time,
		"hours": hours,
		"project": project or None,
		"description": description or None,
		"is_billable": 1,
	}

	existing_name = frappe.db.get_value(
		"Timesheet",
		{"employee": employee, "start_date": log_date, "docstatus": 0},
		"name",
	)

	if existing_name:
		doc = frappe.get_doc("Timesheet", existing_name)
		doc.append("time_logs", log_entry)
		doc.save()
	else:
		company = frappe.db.get_value("Employee", employee, "company")
		doc = frappe.new_doc("Timesheet")
		doc.employee = employee
		doc.company = company
		doc.start_date = log_date
		doc.end_date = log_date
		doc.append("time_logs", log_entry)
		doc.insert()

	frappe.db.commit()
	return doc.name


# Working-hours dashboard
@frappe.whitelist()
def get_working_hours_summary(employee: str, from_date: str, to_date: str) -> dict:
	"""
	Returns daily working hours for an employee between from_date and to_date (inclusive).
	All dates in the range are returned; days with no logs get hours=0.
	"""
	from frappe.utils import getdate, add_days

	rows = frappe.db.sql(
		"""
		SELECT
			DATE(tsd.from_time)  AS log_date,
			SUM(tsd.hours)       AS total_hours
		FROM `tabTimesheet Detail` tsd
		INNER JOIN `tabTimesheet` ts ON tsd.parent = ts.name
		WHERE ts.employee   = %(employee)s
		  AND ts.docstatus  != 2
		  AND DATE(tsd.from_time) BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY DATE(tsd.from_time)
		ORDER BY log_date
		""",
		{"employee": employee, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	# Build a complete date range filled with zeros
	daily: dict[str, float] = {}
	cursor = getdate(from_date)
	end = getdate(to_date)
	while cursor <= end:
		daily[str(cursor)] = 0.0
		cursor = add_days(cursor, 1)

	for row in rows:
		daily[str(row["log_date"])] = round(float(row["total_hours"]), 2)

	daily_list = [{"date": d, "hours": h} for d, h in daily.items()]
	return {"daily": daily_list, "total": round(sum(daily.values()), 2)}


@frappe.whitelist()
def get_employee_project_summary(employee: str, from_date: str, to_date: str) -> list:
	"""
	Returns the employee's hours broken down by project for the given date range,
	ordered by hours descending (top 8).
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			CASE
				WHEN tsd.project IS NULL OR tsd.project = '' THEN 'No Project'
				ELSE tsd.project
			END          AS project,
			SUM(tsd.hours) AS total_hours
		FROM `tabTimesheet Detail` tsd
		INNER JOIN `tabTimesheet` ts ON tsd.parent = ts.name
		WHERE ts.employee   = %(employee)s
		  AND ts.docstatus  != 2
		  AND DATE(tsd.from_time) BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY project
		ORDER BY total_hours DESC
		LIMIT 8
		""",
		{"employee": employee, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	return [{"project": r["project"], "hours": round(float(r["total_hours"]), 2)} for r in rows]


@frappe.whitelist()
def get_team_working_hours_summary(from_date: str, to_date: str) -> list[dict]:
	"""
	Returns working-hours totals for all active employees who logged time in the
	given period, together with each employee's IANA timezone (sourced from their
	approved Employee Schedule, if one exists).

	The caller can use the timezone values to compute UTC-offset differences
	and display how far ahead/behind each colleague is relative to the viewer.

	Returns up to 25 employees, ordered by total hours descending.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			ts.employee,
			MAX(e.employee_name) AS employee_name,
			ROUND(SUM(tsd.hours), 1) AS total_hours
		FROM `tabTimesheet Detail` tsd
		INNER JOIN `tabTimesheet`  ts ON tsd.parent = ts.name
		INNER JOIN `tabEmployee`   e  ON e.name = ts.employee
		WHERE ts.docstatus != 2
		  AND e.status = 'Active'
		  AND DATE(tsd.from_time) BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY ts.employee
		ORDER BY total_hours DESC
		LIMIT 25
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	if not rows:
		return []

	# Look up each employee's timezone from their most-recently approved schedule
	employee_ids = [r["employee"] for r in rows]
	tz_map = {
		s["employee"]: s["timezone"]
		for s in frappe.get_all(
			"Employee Schedule",
			filters={"employee": ["in", employee_ids], "status": "Approved"},
			fields=["employee", "timezone"],
		)
		if s.get("timezone")
	}

	return [
		{
			"employee": r["employee"],
			"employee_name": r["employee_name"] or r["employee"],
			"total_hours": float(r["total_hours"]),
			"timezone": tz_map.get(r["employee"], ""),
		}
		for r in rows
	]


# ── Employee Holiday API ──────────────────────────────────────────────────────


def _get_employee_for_user(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


def _is_hr_or_admin():
	hr_roles = {"HR Manager", "HR User", "System Manager", "Administrator"}
	return bool(hr_roles & set(frappe.get_roles(frappe.session.user)))


@frappe.whitelist()
def get_employee_holiday_for_year(year: str = None) -> dict:
	"""Return the current employee's Employee Holiday record for *year* (default: current year)."""
	import datetime

	year = int(year) if year else datetime.date.today().year
	employee = _get_employee_for_user()
	if not employee:
		return None

	names = frappe.get_list(
		"Employee Holiday",
		filters={"employee": employee, "year": year},
		fields=["name"],
		limit=1,
		order_by="modified desc",
	)
	if not names:
		return None

	return frappe.get_doc("Employee Holiday", names[0]["name"]).as_dict()


@frappe.whitelist()
def save_employee_holiday_draft(year: str, dates: str) -> dict:
	"""
	Upsert a Draft Employee Holiday record for the current employee.
	*dates* is a JSON array of 'YYYY-MM-DD' strings.
	"""
	import json

	year = int(year)
	dates_list = json.loads(dates) if isinstance(dates, str) else list(dates)

	employee = _get_employee_for_user()
	if not employee:
		frappe.throw(_("No active employee record found for the current user."))

	# Only allowed on Draft records
	existing_name = frappe.db.get_value(
		"Employee Holiday",
		{"employee": employee, "year": year, "status": "Draft"},
		"name",
	)

	if existing_name:
		doc = frappe.get_doc("Employee Holiday", existing_name)
	else:
		# Make sure there isn't a non-Draft record already
		non_draft = frappe.db.get_value(
			"Employee Holiday",
			{"employee": employee, "year": year, "status": ["not in", ["Draft", "Rejected"]]},
			"name",
		)
		if non_draft:
			frappe.throw(
				_("A holiday request for {0} already exists and cannot be modified.").format(year)
			)

		doc = frappe.new_doc("Employee Holiday")
		doc.employee = employee
		doc.year = year
		doc.status = "Draft"

	doc.set("holidays", [])
	for date_str in dates_list:
		doc.append("holidays", {"date": date_str, "description": "Holiday"})

	doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
def submit_employee_holidays(name: str) -> dict:
	"""Submit an employee's Draft holiday request (locks it for HR review)."""
	doc = frappe.get_doc("Employee Holiday", name)

	# Ownership check
	employee = _get_employee_for_user()
	if doc.employee != employee and not _is_hr_or_admin():
		frappe.throw(_("You can only submit your own holiday request."))

	if doc.status != "Draft":
		frappe.throw(_("Only Draft holiday requests can be submitted."))

	if len(doc.holidays) != 15:
		frappe.throw(
			_("You must select exactly 15 holiday dates. Currently selected: {0}").format(
				len(doc.holidays)
			)
		)

	doc.status = "Submitted"
	doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
def approve_employee_holiday(name: str) -> dict:
	"""Approve a Submitted holiday request and auto-generate the Holiday List (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can approve holiday requests."))

	doc = frappe.get_doc("Employee Holiday", name)
	if doc.status != "Submitted":
		frappe.throw(_("Only Submitted holiday requests can be approved."))

	doc.status = "Approved"
	doc.save(ignore_permissions=True)

	# _create_holiday_list is called from on_update, but we also call it
	# directly here so we can return the generated list name immediately.
	if not doc.holiday_list:
		doc._create_holiday_list()

	doc.reload()
	return {"status": "Approved", "holiday_list": doc.holiday_list, "name": doc.name}


@frappe.whitelist()
def reject_employee_holiday(name: str) -> dict:
	"""Reject a Submitted holiday request (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can reject holiday requests."))

	doc = frappe.get_doc("Employee Holiday", name)
	if doc.status not in ("Submitted", "Approved"):
		frappe.throw(_("Only Submitted or Approved holiday requests can be rejected."))

	doc.status = "Rejected"
	doc.save(ignore_permissions=True)
	return {"status": "Rejected", "name": doc.name}


@frappe.whitelist()
def get_pending_holiday_approvals() -> list[dict]:
	"""List all Submitted holiday requests (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can view pending holiday approvals."))

	return frappe.get_list(
		"Employee Holiday",
		filters={"status": "Submitted"},
		fields=["name", "employee", "employee_name", "year", "status", "modified"],
		order_by="modified desc",
	)


@frappe.whitelist()
def get_holiday_approval_detail(name: str) -> dict:
	"""Full detail of a holiday request, including all dates (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can view holiday approval details."))

	return frappe.get_doc("Employee Holiday", name).as_dict()


# ── Employee Schedule API ─────────────────────────────────────────────────────

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@frappe.whitelist()
def get_my_schedule(year: str = None) -> dict:
	"""Return the current employee's approved/submitted/draft schedule for the year."""
	import datetime as _dt

	year = int(year) if year else _dt.date.today().year
	employee = _get_employee_for_user()
	if not employee:
		return None

	names = frappe.get_list(
		"Employee Schedule",
		filters={"employee": employee, "year": year},
		fields=["name"],
		limit=1,
		order_by="modified desc",
	)
	if not names:
		return None

	return frappe.get_doc("Employee Schedule", names[0]["name"]).as_dict()


@frappe.whitelist()
def save_schedule_draft(year: str, timezone: str, days: str) -> dict:
	"""
	Upsert a Draft Employee Schedule for the current employee.
	*days* is a JSON list of {day_of_week, day_type, start_time, end_time}.
	"""
	import json, datetime as _dt

	year = int(year)
	days_list = json.loads(days) if isinstance(days, str) else list(days)
	employee = _get_employee_for_user()
	if not employee:
		frappe.throw(_("No active employee record found for the current user."))

	existing_name = frappe.db.get_value(
		"Employee Schedule",
		{"employee": employee, "year": year, "status": "Draft"},
		"name",
	)

	if existing_name:
		doc = frappe.get_doc("Employee Schedule", existing_name)
	else:
		non_draft = frappe.db.get_value(
			"Employee Schedule",
			{"employee": employee, "year": year, "status": ["not in", ["Draft", "Rejected"]]},
			"name",
		)
		if non_draft:
			frappe.throw(_("A schedule for {0} already exists and cannot be modified.").format(year))
		doc = frappe.new_doc("Employee Schedule")
		doc.employee = employee
		doc.year = year
		doc.status = "Draft"

	doc.timezone = timezone or "America/New_York"
	doc.set("schedule_days", [])
	for d in days_list:
		doc.append(
			"schedule_days",
			{
				"day_of_week": int(d["day_of_week"]),
				"day_name": _DAY_NAMES[int(d["day_of_week"])],
				"day_type": d["day_type"],
				"start_time": d.get("start_time") or None,
				"end_time": d.get("end_time") or None,
			},
		)
	doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
def submit_employee_schedule(name: str) -> dict:
	"""Submit a Draft schedule for HR approval."""
	doc = frappe.get_doc("Employee Schedule", name)
	employee = _get_employee_for_user()
	if doc.employee != employee and not _is_hr_or_admin():
		frappe.throw(_("You can only submit your own schedule."))
	if doc.status != "Draft":
		frappe.throw(_("Only Draft schedules can be submitted."))
	doc.status = "Submitted"
	doc.save(ignore_permissions=True)
	return doc.as_dict()


@frappe.whitelist()
def approve_employee_schedule(name: str) -> dict:
	"""Approve a Submitted schedule (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can approve schedules."))
	doc = frappe.get_doc("Employee Schedule", name)
	if doc.status != "Submitted":
		frappe.throw(_("Only Submitted schedules can be approved."))
	doc.status = "Approved"
	doc.save(ignore_permissions=True)
	return {"status": "Approved", "name": doc.name}


@frappe.whitelist()
def reject_employee_schedule(name: str) -> dict:
	"""Reject a Submitted schedule (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can reject schedules."))
	doc = frappe.get_doc("Employee Schedule", name)
	if doc.status not in ("Submitted", "Approved"):
		frappe.throw(_("Only Submitted or Approved schedules can be rejected."))
	doc.status = "Rejected"
	doc.save(ignore_permissions=True)
	return {"status": "Rejected", "name": doc.name}


@frappe.whitelist()
def get_pending_schedule_approvals() -> list[dict]:
	"""List all Submitted schedules (HR only)."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can view pending schedule approvals."))
	return frappe.get_list(
		"Employee Schedule",
		filters={"status": "Submitted"},
		fields=["name", "employee", "employee_name", "year", "timezone", "status", "modified"],
		order_by="modified desc",
	)


@frappe.whitelist()
def get_schedule_approval_detail(name: str) -> dict:
	"""Full schedule detail for HR review."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR can view schedule details."))
	return frappe.get_doc("Employee Schedule", name).as_dict()


# ── Team Availability API ─────────────────────────────────────────────────────


def _norm_time(t) -> str | None:
	"""
	Return a zero-padded "HH:MM" string from a Frappe Time field.

	Frappe stores Time fields as Python ``datetime.timedelta``.
	``str(timedelta(hours=9))`` produces ``"9:00:00"`` — note the missing leading
	zero.  Slicing ``[:5]`` then gives ``"9:00:"`` (trailing colon), which breaks
	any downstream int conversion.  This helper handles all three possible types
	that Frappe might hand back (timedelta, datetime.time, plain string).
	"""
	import datetime as _dt

	if not t:
		return None
	if isinstance(t, _dt.timedelta):
		total_secs = int(t.total_seconds())
		h = total_secs // 3600
		m = (total_secs % 3600) // 60
		return f"{h:02d}:{m:02d}"
	if isinstance(t, _dt.time):
		return f"{t.hour:02d}:{t.minute:02d}"
	# Fall back: parse the first two colon-separated tokens
	parts = str(t).split(":")
	try:
		h, m = int(parts[0]), int(parts[1])
		return f"{h:02d}:{m:02d}"
	except (ValueError, IndexError):
		return None


@frappe.whitelist()
def get_team_availability(
	start_date: str,
	end_date: str,
	viewer_timezone: str = "America/New_York",
) -> list[dict]:
	"""
	Return availability for all employees with approved schedules.
	Times are converted to viewer_timezone (IANA name, e.g. "America/New_York").
	Defaults to EST for backward compatibility.
	"""
	import datetime as _dt
	import pytz

	start = frappe.utils.getdate(start_date)
	end = frappe.utils.getdate(end_date)

	try:
		viewer_tz = pytz.timezone(viewer_timezone)
	except Exception:
		viewer_tz = pytz.timezone("America/New_York")

	# 1. All approved schedules
	schedule_rows = frappe.get_list(
		"Employee Schedule",
		filters={"status": "Approved"},
		fields=["name", "employee", "employee_name", "timezone"],
	)
	if not schedule_rows:
		return []

	employee_ids = [r["employee"] for r in schedule_rows]

	# Build schedule map: employee_id → {tz, name, days: {0..6 → [{type, start, end}]}}
	# Multiple slots per day_of_week are supported.
	schedule_map = {}
	for row in schedule_rows:
		doc = frappe.get_doc("Employee Schedule", row["name"])
		schedule_map[row["employee"]] = {
			"employee_name": row["employee_name"],
			"timezone": row["timezone"] or "America/New_York",
			"days": {},
		}
		for day in doc.schedule_days:
			dow = int(day.day_of_week)
			slot = {
				"type": (day.day_type or "Off").lower().replace("-", "_").replace(" ", "_"),
				"start": _norm_time(day.start_time),
				"end": _norm_time(day.end_time),
			}
			schedule_map[row["employee"]]["days"].setdefault(dow, []).append(slot)

	# 2. Approved leaves in range
	leaves = frappe.db.get_all(
		"Leave Application",
		filters={
			"employee": ["in", employee_ids],
			"status": "Approved",
			"from_date": ["<=", end_date],
			"to_date": [">=", start_date],
		},
		fields=["employee", "from_date", "to_date", "leave_type"],
	)
	leave_dates: dict[str, dict] = {}
	for lv in leaves:
		emp = lv["employee"]
		if emp not in leave_dates:
			leave_dates[emp] = {}
		d = frappe.utils.getdate(lv["from_date"])
		while d <= frappe.utils.getdate(lv["to_date"]):
			leave_dates[emp][str(d)] = lv["leave_type"]
			d += _dt.timedelta(days=1)

	# 3. Approved personal holidays in range
	personal_holidays: dict[str, set] = {}
	holiday_records = frappe.get_list(
		"Employee Holiday",
		filters={"employee": ["in", employee_ids], "status": "Approved"},
		fields=["name", "employee"],
	)
	for hr_rec in holiday_records:
		emp = hr_rec["employee"]
		if emp not in personal_holidays:
			personal_holidays[emp] = set()
		hol_doc = frappe.get_doc("Employee Holiday", hr_rec["name"])
		for h in hol_doc.holidays:
			personal_holidays[emp].add(str(h.date)[:10])

	# 4. Build result for each employee × date
	def _to_viewer_tz(time_str, date_obj, emp_tz):
		"""Convert a "HH:MM" string from emp_tz on date_obj into viewer_tz "HH:MM"."""
		if not time_str or emp_tz == viewer_tz:
			return time_str
		try:
			parts = str(time_str).split(":")
			h, m = int(parts[0]), int(parts[1])
			dt = emp_tz.localize(_dt.datetime(date_obj.year, date_obj.month, date_obj.day, h, m))
			return dt.astimezone(viewer_tz).strftime("%H:%M")
		except Exception:
			return time_str

	result = []
	for emp_id, sdata in schedule_map.items():
		try:
			emp_tz = pytz.timezone(sdata["timezone"])
		except Exception:
			emp_tz = viewer_tz

		user_id = frappe.db.get_value("Employee", emp_id, "user_id") or ""
		emp_days = {}
		d = start
		while d <= end:
			date_str = str(d)
			dow = d.weekday()  # 0=Mon, 6=Sun
			day_slots = sdata["days"].get(dow, [])  # list of {type, start, end}

			if emp_id in leave_dates and date_str in leave_dates[emp_id]:
				emp_days[date_str] = {
					"override": "leave",
					"override_label": leave_dates[emp_id][date_str],
					"slots": [],
				}
			elif emp_id in personal_holidays and date_str in personal_holidays[emp_id]:
				emp_days[date_str] = {
					"override": "holiday",
					"override_label": "Holiday",
					"slots": [],
				}
			else:
				# Convert each slot's times to viewer's timezone
				converted_slots = []
				for slot in day_slots:
					s_est = _to_viewer_tz(slot["start"], d, emp_tz)
					e_est = _to_viewer_tz(slot["end"], d, emp_tz)
					converted_slots.append({
						"type": slot["type"],
						"start": s_est,
						"end": e_est,
					})
				emp_days[date_str] = {
					"override": None,
					"override_label": None,
					"slots": converted_slots,
				}

			d += _dt.timedelta(days=1)

		result.append(
			{
				"employee": emp_id,
				"employee_name": sdata["employee_name"],
				"user_id": user_id,
				"timezone": sdata["timezone"],
				"days": emp_days,
			}
		)

	# Sort by employee name
	result.sort(key=lambda x: x["employee_name"] or "")
	return result


# ── HR Documents ──────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_hr_documents(category=None):
	"""Return all active HR Documents, optionally filtered by category."""
	filters = {"is_active": 1}
	if category:
		filters["category"] = category
	return frappe.get_all(
		"HR Document",
		filters=filters,
		fields=["name", "title", "url", "category", "description"],
		order_by="category asc, title asc",
	)


@frappe.whitelist()
def get_hr_document_categories():
	"""Return a deduplicated sorted list of active category names."""
	rows = frappe.db.sql(
		"""SELECT DISTINCT category FROM `tabHR Document`
		   WHERE is_active = 1 AND category IS NOT NULL AND category != ''
		   ORDER BY category""",
		as_dict=False,
	)
	return [r[0] for r in rows]


@frappe.whitelist()
def save_hr_document(title, url, category, description=None, name=None):
	"""Create or update an HR Document. Requires HR Manager or HR User role."""
	_require_hr_role()
	if not url.startswith(("http://", "https://")):
		url = "https://" + url
	if name and frappe.db.exists("HR Document", name):
		doc = frappe.get_doc("HR Document", name)
	else:
		doc = frappe.new_doc("HR Document")
	doc.title = title
	doc.url = url
	doc.category = category.strip()
	doc.description = description or ""
	doc.is_active = 1
	doc.save()
	return doc.name


@frappe.whitelist()
def delete_hr_document(name):
	"""Delete an HR Document. Requires HR Manager role."""
	if not _is_hr_or_admin():
		frappe.throw(_("Only HR Managers can delete documents."))
	frappe.delete_doc("HR Document", name, ignore_permissions=False)


def _require_hr_role():
	hr_roles = {"HR Manager", "HR User", "System Manager", "Administrator"}
	if not (hr_roles & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(_("Only HR can manage documents."))
