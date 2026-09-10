import calendar
import datetime

import frappe
from frappe.utils import add_days, getdate, nowdate


PAID_LEAVE_TYPES = ("Paid Leave", "Sick Leave")
VISIBLE_LEAVE_TYPES = (*PAID_LEAVE_TYPES, "Unpaid Leave")
ANNUAL_ALLOCATION = 15
UNPAID_ANNUAL_LIMIT = 10
WORKDAY_HOURS = 8
POLICY_TITLE = "Realtyna Anniversary Leave Policy"


def _anniversary(joining_date: datetime.date, year: int) -> datetime.date:
	last_day = calendar.monthrange(year, joining_date.month)[1]
	return joining_date.replace(year=year, day=min(joining_date.day, last_day))


def get_anniversary_period(employee: str, as_of=None) -> tuple[datetime.date, datetime.date]:
	joining_date = getdate(frappe.db.get_value("Employee", employee, "date_of_joining"))
	date = getdate(as_of or nowdate())
	period_start = _anniversary(joining_date, date.year)
	if period_start > date:
		period_start = _anniversary(joining_date, date.year - 1)
	period_end = add_days(_anniversary(joining_date, period_start.year + 1), -1)
	return period_start, period_end


def ensure_leave_policy() -> str:
	name = frappe.db.get_value("Leave Policy", {"title": POLICY_TITLE}, "name")
	if name:
		return name

	doc = frappe.new_doc("Leave Policy")
	doc.title = POLICY_TITLE
	for leave_type in PAID_LEAVE_TYPES:
		doc.append(
			"leave_policy_details",
			{"leave_type": leave_type, "annual_allocation": ANNUAL_ALLOCATION},
		)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def configure_leave_types() -> None:
	for leave_type in PAID_LEAVE_TYPES:
		frappe.db.set_value(
			"Leave Type",
			leave_type,
			{
				"max_leaves_allowed": 0,
				"max_continuous_days_allowed": 0,
				"is_carry_forward": 1,
				"maximum_carry_forwarded_leaves": 0,
				"expire_carry_forwarded_leaves_after_days": 365,
				"allow_negative": 0,
				"allow_encashment": 1,
				"earning_component": "Leave Encashment",
				"max_encashable_leaves": 0,
				"non_encashable_leaves": 0,
				"include_holiday": 0,
			},
		)

	frappe.db.set_value(
		"Leave Type",
		"Unpaid Leave",
		{
			"is_lwp": 1,
			"max_leaves_allowed": UNPAID_ANNUAL_LIMIT,
			"max_continuous_days_allowed": UNPAID_ANNUAL_LIMIT,
			"allow_negative": 0,
			"include_holiday": 0,
		},
	)


def _cancel_empty_overlapping_allocations(employee, leave_type, period_start, period_end):
	overlaps = frappe.get_all(
		"Leave Allocation",
		filters={
			"employee": employee,
			"leave_type": leave_type,
			"docstatus": 1,
			"from_date": ("<=", period_end),
			"to_date": (">=", period_start),
		},
		pluck="name",
	)

	for name in overlaps:
		allocation = frappe.get_doc("Leave Allocation", name)
		if getdate(allocation.from_date) == period_start and getdate(allocation.to_date) == period_end:
			return allocation.name

		used = frappe.db.exists(
			"Leave Application",
			{
				"employee": employee,
				"leave_type": leave_type,
				"docstatus": ("<", 2),
				"status": ("in", ("Open", "Approved")),
				"from_date": ("<=", allocation.to_date),
				"to_date": (">=", allocation.from_date),
			},
		)
		if used:
			return None

		allocation.flags.ignore_permissions = True
		allocation.cancel()

	return False


def ensure_employee_leave_allocations(employee, as_of=None, policy=None) -> dict:
	if isinstance(employee, str):
		employee_name = employee
	else:
		if employee.status != "Active" or not employee.date_of_joining:
			return {}
		employee_name = employee.name

	status, joining_date = frappe.db.get_value(
		"Employee", employee_name, ["status", "date_of_joining"]
	)
	date = getdate(as_of or nowdate())
	if status != "Active" or not joining_date or getdate(joining_date) > date:
		return {}

	policy = policy or ensure_leave_policy()
	period_start, period_end = get_anniversary_period(employee_name, date)
	created = {}

	for leave_type in PAID_LEAVE_TYPES:
		existing = _cancel_empty_overlapping_allocations(
			employee_name, leave_type, period_start, period_end
		)
		if existing:
			created[leave_type] = existing
			continue
		if existing is None:
			created[leave_type] = "Skipped: existing leave activity"
			continue

		previous = frappe.db.exists(
			"Leave Allocation",
			{
				"employee": employee_name,
				"leave_type": leave_type,
				"docstatus": 1,
				"to_date": ("<", period_start),
			},
		)
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee_name,
				"leave_type": leave_type,
				"from_date": period_start,
				"to_date": period_end,
				"new_leaves_allocated": ANNUAL_ALLOCATION,
				"carry_forward": 1 if previous else 0,
				"leave_policy": policy,
			}
		)
		allocation.insert(ignore_permissions=True)
		allocation.submit()
		created[leave_type] = allocation.name

	return created


def ensure_current_leave_allocations(doc=None, method=None) -> dict:
	policy = ensure_leave_policy()
	result = {}
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "date_of_joining": ("<=", nowdate())},
		pluck="name",
	)
	for employee in employees:
		result[employee] = ensure_employee_leave_allocations(employee, policy=policy)
	return result


def ensure_employee_current_leave_allocations(doc, method=None) -> None:
	if doc.status == "Active" and doc.date_of_joining and getdate(doc.date_of_joining) <= getdate():
		ensure_employee_leave_allocations(doc)


def _weekend_dates(year: int):
	date = datetime.date(year, 1, 1)
	end = datetime.date(year, 12, 31)
	while date <= end:
		if date.weekday() in (5, 6):
			yield date
		date = add_days(date, 1)


def ensure_company_weekend_lists(year=None) -> dict:
	year = int(year or getdate().year)
	result = {}
	companies = frappe.get_all(
		"Employee", filters={"status": "Active"}, distinct=True, pluck="company"
	)
	for company in filter(None, companies):
		list_name = f"{company} Weekends - {year}"
		expected_dates = list(_weekend_dates(year))
		if frappe.db.exists("Holiday List", list_name):
			holiday_list = frappe.get_doc("Holiday List", list_name)
			current_dates = {getdate(row.holiday_date) for row in holiday_list.holidays}
			if current_dates != set(expected_dates) or any(not row.weekly_off for row in holiday_list.holidays):
				holiday_list.set("holidays", [])
				for date in expected_dates:
					holiday_list.append(
						"holidays",
						{"holiday_date": date, "description": "Weekend", "weekly_off": 1},
					)
				holiday_list.save(ignore_permissions=True)
		else:
			holiday_list = frappe.new_doc("Holiday List")
			holiday_list.holiday_list_name = list_name
			holiday_list.from_date = f"{year}-01-01"
			holiday_list.to_date = f"{year}-12-31"
			for date in expected_dates:
				holiday_list.append(
					"holidays",
					{"holiday_date": date, "description": "Weekend", "weekly_off": 1},
				)
			holiday_list.save(ignore_permissions=True)

		from_date = getdate(f"{year}-01-01")
		assignment_name = frappe.db.get_value(
			"Holiday List Assignment",
			{"assigned_to": company, "from_date": from_date, "docstatus": 1},
			"name",
		)
		if assignment_name:
			frappe.db.set_value(
				"Holiday List Assignment", assignment_name, "holiday_list", list_name
			)
		else:
			assignment = frappe.get_doc(
				{
					"doctype": "Holiday List Assignment",
					"applicable_for": "Company",
					"assigned_to": company,
					"holiday_list": list_name,
					"from_date": from_date,
				}
			)
			assignment.insert(ignore_permissions=True)
			assignment.submit()
			assignment_name = assignment.name
		result[company] = assignment_name
	return result


def rebuild_approved_employee_holiday_lists(year=None) -> dict:
	year = int(year or getdate().year)
	result = {}
	for name in frappe.get_all(
		"Employee Holiday",
		filters={"year": year, "status": "Approved"},
		pluck="name",
	):
		doc = frappe.get_doc("Employee Holiday", name)
		doc._create_holiday_list()
		result[name] = doc.holiday_list
	return result


def run_daily_leave_policy_maintenance() -> None:
	ensure_company_weekend_lists()
	ensure_current_leave_allocations()


@frappe.whitelist()
def apply_realtyna_leave_policy() -> dict:
	configure_leave_types()
	policy = ensure_leave_policy()
	weekends = ensure_company_weekend_lists()
	employee_holidays = rebuild_approved_employee_holiday_lists()
	allocations = ensure_current_leave_allocations()
	frappe.clear_cache()
	return {
		"policy": policy,
		"weekends": weekends,
		"employee_holidays": employee_holidays,
		"allocations": allocations,
	}
