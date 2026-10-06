from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

from hrms.api.weekly_timesheet import _is_hr


MAX_ENTRIES = 10000
STATUSES = {"Draft", "Pending Project Approval", "Pending HR Review", "Correction Required", "Closed", "Submitted"}


def _project_scope():
	if _is_hr():
		return None
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
	projects = set()
	if employee:
		for field in ("custom_project_lead", "custom_project_manager"):
			projects.update(frappe.get_all("Project", filters={field: employee}, pluck="name"))
	if not projects:
		frappe.throw(_("You do not have access to management reports."), frappe.PermissionError)
	return projects


def _date_range(from_date, to_date):
	start, end = getdate(from_date or add_days(today(), -89)), getdate(to_date or today())
	if start > end or (end - start).days > 365:
		frappe.throw(_("Choose a date range of no more than one year."))
	return start, end


def _read_entries(start, end, scope, project=None, employee=None, activity_type=None, company=None):
	ts, detail = frappe.qb.DocType("Timesheet"), frappe.qb.DocType("Timesheet Detail")
	query = (
		frappe.qb.from_(detail).join(ts).on(detail.parent == ts.name)
		.select(detail.name, ts.name.as_("timesheet"), ts.employee, ts.employee_name,
			ts.docstatus, ts.company, ts.custom_is_weekly, ts.custom_weekly_status, detail.project, detail.activity_type,
			detail.from_time, detail.to_time, detail.hours, detail.custom_return_reason)
		.where((ts.docstatus < 2) & (detail.parenttype == "Timesheet")
			& (detail.from_time >= str(start)) & (detail.from_time < str(add_days(end, 1))))
	)
	if scope is not None:
		query = query.where(detail.project.isin(sorted(scope)))
	for column, value in ((detail.project, project), (ts.employee, employee), (detail.activity_type, activity_type), (ts.company, company)):
		if value:
			query = query.where(column == value)
	rows = query.orderby(detail.from_time).limit(MAX_ENTRIES + 1).run(as_dict=True)
	if len(rows) > MAX_ENTRIES:
		frappe.throw(_("Too many time entries. Narrow the date range, project or employee filter."))
	return rows


def _status(row):
	return row.get("custom_weekly_status") or ("Submitted" if row.docstatus == 1 else "Draft")


def _aggregate(entries, group_by):
	groups = {}
	statuses = defaultdict(float)
	projects, employees = set(), set()
	for row in entries:
		status = _status(row)
		hours = flt(row.hours)
		statuses[status] += hours
		projects.add(row.project)
		employees.add(row.employee)
		key = str(row.from_time)[:7] if group_by == "month" else (row.get(group_by) or "Unassigned")
		label = row.employee_name if group_by == "employee" else row.get("project_label") if group_by == "project" else key
		group = groups.setdefault((row.get("company"), key), {"company": row.get("company"), "key": key, "label": label or key, "hours": 0.0, "entries": 0, "status_hours": defaultdict(float)})
		group["hours"] += hours
		group["entries"] += 1
		group["status_hours"][status] += hours
	for group in groups.values():
		group["status_hours"] = dict(group["status_hours"])
	return {
		"rows": sorted(groups.values(), key=lambda row: (row.get("company") or "", row["key"] if group_by == "month" else (-row["hours"], row["label"]))),
		"totals": {"hours": sum(statuses.values()), "entries": len(entries),
			"projects": len(projects - {None, ""}), "employees": len(employees - {None, ""}),
			"status_hours": dict(statuses)},
	}


@frappe.whitelist()
def get_time_history(from_date=None, to_date=None, project=None, employee=None, activity_type=None, status=None, group_by="project", company=None):
	"""Read-only analysis of the original time entries; never an approval queue."""
	scope = _project_scope()
	if project and scope is not None and project not in scope:
		frappe.throw(_("You do not have access to this project."), frappe.PermissionError)
	if group_by not in {"project", "employee", "activity_type", "month"} or status and status not in STATUSES:
		frappe.throw(_("Invalid report filter."))
	start, end = _date_range(from_date, to_date)
	entries = _read_entries(start, end, scope, project, employee, activity_type, company)
	labels = {p.name: p.project_name for p in frappe.get_all("Project",
		filters={"name": ("in", sorted({r.project for r in entries if r.project}))}, fields=["name", "project_name"])} if entries else {}
	for row in entries:
		row.project_label = labels.get(row.project) or row.project or _("Unassigned")
		row.activity_type = row.activity_type or "Unassigned"
		row.status = _status(row)
	if status:
		entries = [row for row in entries if row.status == status]
	result = _aggregate(entries, group_by)
	result.update({"from_date": str(start), "to_date": str(end), "group_by": group_by, "entries": entries})
	return result


@frappe.whitelist()
def get_review_companies():
	"""Company choices for the existing review/report scope."""
	scope = _project_scope()
	if scope is None:
		return frappe.get_list("Company", pluck="name", order_by="name asc", limit_page_length=0)
	filters = {} if scope is None else {"name": ("in", sorted(scope))}
	companies = {row.company for row in frappe.get_all("Project", filters=filters, fields=["company"]) if row.company}
	return frappe.get_list("Company", filters={"name": ("in", sorted(companies))}, pluck="name", order_by="name asc", limit_page_length=0) if companies else []


@frappe.whitelist()
def get_daily_project_summary(week_start=None, company=None):
	"""Read-only project coverage, independent of the project approval queue."""
	from hrms.api.weekly_timesheet import _week_bounds
	scope = _project_scope()
	start, end = _week_bounds(week_start)
	filters = {"company": company} if company else {}
	if scope is not None:
		filters["name"] = ("in", sorted(scope))
	projects = frappe.get_all("Project", filters=filters, fields=["name", "project_name", "company", "status"], order_by="company asc, project_name asc", limit_page_length=0)
	if not projects:
		return []
	entries = _read_entries(start, end, {p.name for p in projects})
	approvals = frappe.get_all("Timesheet Project Approval", filters={"parent": ("in", sorted({r.timesheet for r in entries}))}, fields=["parent", "project", "status"], limit_page_length=0) if entries else []
	states = {(a.parent, a.project): a.status for a in approvals}
	grouped = defaultdict(dict)
	days = [str(add_days(start, offset)) for offset in range(7)]
	for row in entries:
		member = grouped[row.project].setdefault(row.employee, {"employee": row.employee, "employee_name": row.employee_name, "daily_hours": [0.0] * 7, "weekly_total": 0.0, "activity_types": set(), "status": states.get((row.timesheet, row.project), "Draft")})
		if not row.custom_is_weekly:
			member["includes_legacy_entries"] = True
		day = str(row.from_time)[:10]
		if day in days:
			member["daily_hours"][days.index(day)] += flt(row.hours)
			member["weekly_total"] += flt(row.hours)
		if row.activity_type:
			member["activity_types"].add(row.activity_type)
	result = []
	for project in projects:
		members = sorted(grouped[project.name].values(), key=lambda r: r["employee_name"] or "")
		for member in members:
			member["activity_types"] = sorted(member["activity_types"])
		result.append({"project": project.name, "project_label": project.project_name or project.name, "company": project.company, "week_start": str(start), "week_end": str(end), "days": days, "members": members})
	return result
