import frappe
from frappe import _


HR_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}
COMPANY_DIRECTOR_ROLE = "Company Desk Administrator"
REVIEW_COUNTS = {
	"hr-timesheets": None,
	"Leave Application": {"status": ["in", ["Open", "Approved", "Rejected"]], "docstatus": 0},
	"Expense Claim": {"approval_status": "Draft", "docstatus": 0},
	"Employee Holiday": {"status": "Submitted"},
	"Employee Schedule": {"status": "Submitted"},
	"Employee Invoice": {"status": "Pending HR Review"},
}
CARD_ICONS = {
	"hr-timesheets": "list-alt", "project-timesheets": "hr", "time-history": "chart",
	"Leave Application": "today", "Expense Claim": "expenses",
	"Employee Holiday": "today", "Employee Schedule": "gantt",
	"Employee Invoice": "small-file", "User": "permission", "Employee": "customer", "Project": "projects",
}


def _has_any_permission(doctype: str, *permissions: str) -> bool:
	return frappe.has_permission(doctype, "read") and any(
		frappe.has_permission(doctype, permission) for permission in permissions
	)


def _is_approver(parentfield: str, employee_field: str) -> bool:
	user = frappe.session.user
	return bool(
		frappe.db.exists("Employee", {employee_field: user, "status": "Active"})
		or frappe.db.exists(
			"Department Approver", {"parentfield": parentfield, "approver": user}
		)
	)


def _admin_desk_sections() -> list[dict]:
	from hrms.api.weekly_timesheet import is_project_lead, is_project_manager
	from hrms.utils.master_access import can_manage_master

	roles = set(frappe.get_roles())
	is_company_director = COMPANY_DIRECTOR_ROLE in roles
	is_hr = bool(roles & HR_ROLES) or is_company_director
	can_review_projects = is_hr or is_project_lead() or is_project_manager()
	sections = [
		{"label": _("Timesheet Reviews"), "items": []},
		{"label": _("Contractor Requests"), "items": []},
		{"label": _("HR Approvals"), "items": []},
		{"label": _("People and Projects"), "items": []},
	]

	if can_review_projects:
		sections[0]["items"].append(
			{"label": _("Team Timesheets"), "route": "/desk/admin-reviews/project-timesheets"}
		)
	if roles & {"HR Manager", "HR User"} or is_company_director:
		sections[0]["items"].insert(0,
			{"label": _("HR Weekly Timesheet Review"), "route": "/desk/admin-reviews/hr-timesheets"}
		)

	if is_hr or is_company_director or (
		_is_approver("leave_approvers", "leave_approver")
		and frappe.has_permission("Leave Application", "write")
	):
		sections[1]["items"].append(
			{"label": _("Leave Requests"), "route": "/desk/leave-application", "doctype": "Leave Application", "filters": {"status": ["in", ["Open", "Approved", "Rejected"]], "docstatus": 0}}
		)
	if is_hr or is_company_director or (
		_is_approver("expense_approvers", "expense_approver")
		and frappe.has_permission("Expense Claim", "write")
	):
		sections[1]["items"].append(
			{"label": _("Expense Requests"), "route": "/desk/expense-claim", "doctype": "Expense Claim", "filters": {"approval_status": "Draft", "docstatus": 0}}
		)

	if is_hr:
		sections[2]["items"].extend(
			[
				{"label": _("Holiday Approvals"), "route": "/desk/employee-holiday", "doctype": "Employee Holiday", "filters": {"status": "Submitted"}},
				{"label": _("Schedule Approvals"), "route": "/desk/employee-schedule", "doctype": "Employee Schedule", "filters": {"status": "Submitted"}},
				{"label": _("Invoices"), "route": "/desk/employee-invoice", "doctype": "Employee Invoice", "filters": {"status": ["not in", ["Draft", "Cancelled"]]}},
			]
		)

	for doctype, label, route in (
		("User", _("Users"), "/desk/user"),
		("Employee", _("Contractors"), "/desk/employee"),
		("Project", _("Projects"), "/desk/project"),
	):
		if can_manage_master(doctype) and _has_any_permission(doctype, "create", "write"):
			sections[3]["items"].append({"label": label, "route": route, "doctype": doctype})
	if can_review_projects:
		sections.append({"label": _("Management Reports"), "items": [
			{"label": _("Time History"), "route": "/desk/admin-reviews/time-history"}
		]})

	for section in sections:
		for item in section["items"]:
			key = item.get("doctype") or item["route"].rsplit("/", 1)[-1]
			item["icon"] = CARD_ICONS[key]
			if key in REVIEW_COUNTS:
				item["count_key"] = key
	return [section for section in sections if section["items"]]


@frappe.whitelist()
def get_admin_desk_sections() -> list[dict]:
	return _admin_desk_sections()


@frappe.whitelist()
def get_admin_desk_counts() -> dict:
	"""Count only visible review queues, under the caller's row permissions."""
	from hrms.api.weekly_timesheet import get_hr_weekly_timesheet_queue
	from hrms.utils.personal_scope import _is_manager, APPROVER_FIELDS

	counts = {}
	for section in _admin_desk_sections():
		for item in section["items"]:
			key = item.get("count_key")
			if not key:
				continue
			doctype = "Timesheet" if key == "hr-timesheets" else key
			if not frappe.has_permission(doctype, "read"):
				counts[key] = None
				continue
			if key == "hr-timesheets":
				weeks = get_hr_weekly_timesheet_queue("current")
				counts[key] = len(weeks)
				if len(weeks) >= 500:
					counts["hr-timesheets-capped"] = True
				counts["hr-timesheets-ready"] = sum(int(row["ready_for_hr_close"]) for row in weeks)
			else:
				filters = dict(REVIEW_COUNTS[key])
				if key in APPROVER_FIELDS and not _is_manager(frappe.session.user):
					filters[APPROVER_FIELDS[key]] = frappe.session.user
				rows = frappe.get_list(doctype, filters=filters, fields=[{"COUNT": "name", "as": "total"}], limit_page_length=1)
				counts[key] = int(rows[0].total or 0) if rows else 0
	return counts


@frappe.whitelist()
def get_admin_review_requests(limit: int = 200) -> list[dict]:
	from hrms.api import get_expense_claims, get_leave_applications

	limit = min(max(int(limit), 1), 500)
	approver = frappe.session.user
	employee = frappe.db.get_value(
		"Employee", {"user_id": approver, "status": "Active"}, "name"
	) or ""
	requests = []
	company_director = COMPANY_DIRECTOR_ROLE in set(frappe.get_roles())
	for doctype, getter in (
		("Leave Application", get_leave_applications),
		("Expense Claim", get_expense_claims),
	):
		if not frappe.has_permission(doctype, "read"):
			continue
		workflow = frappe.db.exists("Workflow", {"document_type": doctype, "is_active": 1})
		request_employee = "" if company_director else employee
		request_approver = approver if not company_director or workflow else None
		for row in getter(request_employee, request_approver, True, limit):
			row["doctype"] = doctype
			requests.append(row)

	return sorted(requests, key=lambda row: row.get("creation") or "", reverse=True)[:limit]


def set_admin_reviews_home(bootinfo: dict) -> None:
	sections = _admin_desk_sections() if frappe.session.user != "Guest" else []
	if not sections:
		return

	from frappe.desk.desk_page import get as get_desk_page

	page = get_desk_page("admin-reviews")
	if not any(doc.get("name") == page.name and doc.get("doctype") == "Page" for doc in bootinfo.docs):
		bootinfo.docs.append(page)
	bootinfo.home_page = page.name
	bootinfo.hrms_can_review_project_timesheets = any(
		item["route"] == "/desk/admin-reviews/project-timesheets"
		for section in sections for item in section["items"]
	)
	# Frappe v16 accepts session-specific sidebar definitions in boot data.
	# Records and permissions are unchanged; only the managerial navigation changes.
	if "workspace_sidebar_item" in bootinfo:
		items = []
		bootinfo.workspace_sidebar_item = {
			"admin reviews": {"name": "Admin Reviews", "label": "Admin Reviews", "app": "hrms", "module": "HR", "items": items, "module_onboarding": None}
		}
		bootinfo.hrms_admin_sidebar = True
		for icon in bootinfo.get("desktop_icons", []):
			if icon.get("app") == "erpnext" and icon.get("label") not in {"HR", "Projects"}:
				icon["hidden"] = 1
