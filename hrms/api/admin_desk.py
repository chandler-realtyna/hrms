import frappe
from frappe import _


HR_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}
COMPANY_DIRECTOR_ROLE = "Company Desk Administrator"


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

	roles = set(frappe.get_roles())
	is_company_director = COMPANY_DIRECTOR_ROLE in roles
	is_hr = bool(roles & HR_ROLES) or is_company_director
	sections = [
		{"label": _("Timesheet Reviews"), "items": []},
		{"label": _("Employee Requests"), "items": []},
		{"label": _("HR Approvals"), "items": []},
		{"label": _("People and Projects"), "items": []},
	]

	if is_project_lead() or is_company_director:
		sections[0]["items"].append(
			{"label": _("Project Timesheets"), "route": "/desk/admin-reviews/project-timesheets"}
		)
	if is_project_manager() or is_company_director:
		sections[0]["items"].append(
			{"label": _("Project Weekly Reports"), "route": "/desk/admin-reviews/project-reports"}
		)
	if roles & {"HR Manager", "HR User"} or is_company_director:
		sections[0]["items"].append(
			{"label": _("HR Weekly Timesheet Review"), "route": "/desk/admin-reviews/hr-timesheets"}
		)

	if is_hr or is_company_director or (
		_is_approver("leave_approvers", "leave_approver")
		and frappe.has_permission("Leave Application", "write")
	):
		sections[1]["items"].append(
			{"label": _("Leave Requests"), "route": "/desk/leave-application", "doctype": "Leave Application", "filters": {"status": "Open", "docstatus": 0}}
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
				{"label": _("Employee Invoices"), "route": "/desk/employee-invoice", "doctype": "Employee Invoice", "filters": {"status": ["not in", ["Draft", "Cancelled"]]}},
			]
		)

	for doctype, label, route in (
		("User", _("Users"), "/desk/user"),
		("Employee", _("Employees"), "/desk/employee"),
		("Project", _("Projects"), "/desk/project"),
	):
		if _has_any_permission(doctype, "create", "write"):
			sections[3]["items"].append({"label": label, "route": route, "doctype": doctype})

	return [section for section in sections if section["items"]]


@frappe.whitelist()
def get_admin_desk_sections() -> list[dict]:
	return _admin_desk_sections()


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
	# Frappe v16 accepts session-specific sidebar definitions in boot data.
	# Records and permissions are unchanged; only the managerial navigation changes.
	if "workspace_sidebar_item" in bootinfo:
		items = [{"type": "Link", "label": _("Admin Reviews"), "link_type": "Page", "link_to": "admin-reviews", "icon": "home"}]
		for section in sections:
			items.append({"type": "Section Break", "label": section["label"], "collapsible": 0})
			for item in section["items"]:
				link = {"type": "Link", "label": item["label"], "child": 1, "icon": "list"}
				if item.get("doctype"):
					link.update({"link_type": "DocType", "link_to": item["doctype"], "route_options": frappe.as_json(item.get("filters") or {})})
				else:
					link.update({"link_type": "URL", "url": item["route"]})
				items.append(link)
		bootinfo.workspace_sidebar_item = {
			"admin reviews": {"name": "Admin Reviews", "label": "Admin Reviews", "app": "hrms", "module": "HR", "items": items, "module_onboarding": None}
		}
		bootinfo.hrms_admin_sidebar = True
		for icon in bootinfo.get("desktop_icons", []):
			if icon.get("app") == "erpnext" and icon.get("label") not in {"HR", "Projects"}:
				icon["hidden"] = 1
