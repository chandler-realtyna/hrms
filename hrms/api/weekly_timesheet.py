from __future__ import annotations

from datetime import datetime, time

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate


WEEKLY_DRAFT = "Draft"
PENDING_PROJECT = "Pending Project Approval"
CORRECTION_REQUIRED = "Correction Required"
PENDING_HR = "Pending HR Review"
CLOSED = "Closed"

APPROVAL_PENDING = "Pending"
APPROVAL_APPROVED = "Approved"
APPROVAL_RETURNED = "Returned"
APPROVAL_HR = "HR Review"

HR_ROLES = {"HR Manager", "HR User"}
ALLOWED_EMPLOYEE_STATES = {WEEKLY_DRAFT, CORRECTION_REQUIRED}


def _week_bounds(value=None):
	day = getdate(value or nowdate())
	days_since_sunday = (day.weekday() + 1) % 7
	week_start = add_days(day, -days_since_sunday)
	return week_start, add_days(week_start, 6)


def _current_employee():
	employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user, "status": "Active"},
		["name", "employee_name", "company", "user_id"],
		as_dict=True,
	)
	if not employee:
		frappe.throw(_("No active employee is linked to your user account."), frappe.PermissionError)
	return employee


def _employee_user(employee: str) -> str | None:
	return frappe.db.get_value("Employee", employee, "user_id")


def _is_hr(user: str | None = None) -> bool:
	return bool(HR_ROLES.intersection(frappe.get_roles(user or frappe.session.user)))


def _require_hr():
	if not _is_hr():
		frappe.throw(_("Only HR can complete this action."), frappe.PermissionError)


def _project_manager_user(project: str) -> str | None:
	"""Legacy approver lookup (Project Manager). Kept for backward
	compatibility of old approval rows and the legacy manager report.
	New timesheet approval logic uses _project_lead_user instead."""
	manager = frappe.db.get_value("Project", project, "custom_project_manager")
	if not manager:
		return None
	user = frappe.db.get_value("Employee", {"name": manager, "status": "Active"}, "user_id")
	if not user:
		frappe.throw(
			_("The Project Manager for {0} does not have a user account.").format(
				frappe.bold(project)
			)
		)
	return user


def _project_lead_user(project: str) -> str | None:
	"""User id of the active Project Lead, or None when the project has no
	usable lead (missing, inactive, or without a user account). Missing leads
	route to HR review instead of blocking submission."""
	lead = frappe.db.get_value("Project", project, "custom_project_lead")
	if not lead:
		return None
	return frappe.db.get_value("Employee", {"name": lead, "status": "Active"}, "user_id") or None


def _project_lead_employee(project: str) -> str | None:
	"""Employee id of the active Project Lead, or None."""
	lead = frappe.db.get_value("Project", project, "custom_project_lead")
	if not lead:
		return None
	if not frappe.db.get_value("Employee", {"name": lead, "status": "Active"}, "name"):
		return None
	return lead


def is_project_lead(user: str | None = None) -> bool:
	user = user or frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
	if not employee:
		return False
	return bool(
		frappe.db.exists(
			"Project", {"custom_project_lead": employee, "status": "Open"}
		)
	)


def is_project_manager(user: str | None = None) -> bool:
	user = user or frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
	if not employee:
		return False
	return bool(
		frappe.db.exists(
			"Project", {"custom_project_manager": employee, "status": "Open"}
		)
	)


def _assert_employee_owns(doc):
	if _employee_user(doc.employee) != frappe.session.user:
		frappe.throw(_("You can only access your own weekly timesheet."), frappe.PermissionError)


def _notify(users, subject: str, message: str, timesheet: str):
	for user in set(filter(None, users)):
		if user == frappe.session.user:
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": message,
				"for_user": user,
				"type": "Alert",
				"document_type": "Timesheet",
				"document_name": timesheet,
			}
		).insert(ignore_permissions=True)
		# Mirror into PWA Notification as well: Notification Log is desk-only,
		# while the bell badge and Notifications page read PWA Notification.
		# reference_document_type must be a real DocType ("Timer" is not one).
		if not frappe.db.exists(
			"PWA Notification",
			{
				"to_user": user,
				"reference_document_type": "Timesheet",
				"reference_document_name": timesheet,
			},
		):
			pwa_notification = frappe.new_doc("PWA Notification")
			pwa_notification.from_user = frappe.session.user
			pwa_notification.to_user = user
			pwa_notification.message = f"{subject}: {message}"
			pwa_notification.reference_document_type = "Timesheet"
			pwa_notification.reference_document_name = timesheet
			pwa_notification.insert(ignore_permissions=True)


def _notify_project_report(user: str, project: str, week_start):
	reference_name = f"{project}|{week_start}"
	if frappe.db.exists(
		"PWA Notification",
		{
			"to_user": user,
			"reference_document_type": "Timesheet Project Approval",
			"reference_document_name": reference_name,
		},
	):
		return
	notification = frappe.new_doc("PWA Notification")
	notification.from_user = frappe.session.user
	notification.to_user = user
	notification.message = _("A weekly report for project {0} is ready for review.").format(
		frappe.bold(project)
	)
	notification.reference_document_type = "Timesheet Project Approval"
	notification.reference_document_name = reference_name
	notification.insert(ignore_permissions=True)


def _hr_users():
	return frappe.get_all(
		"Has Role",
		filters={"role": "HR Manager", "parenttype": "User"},
		pluck="parent",
		limit_page_length=100,
	)


def _serialize_row(row):
	return {
		"name": row.name,
		"project": row.project,
		"activity_type": row.activity_type,
		"description": row.description,
		"from_time": str(row.from_time) if row.from_time else None,
		"to_time": str(row.to_time) if row.to_time else None,
		"hours": flt(row.hours, 4),
		"is_billable": cint(row.is_billable),
	}


def _serialize_weekly(doc):
	editable_projects = []
	if doc.custom_weekly_status == CORRECTION_REQUIRED:
		editable_projects = [
			row.project for row in doc.custom_project_approvals if row.status == APPROVAL_RETURNED
		]

	return {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"company": doc.company,
		"docstatus": doc.docstatus,
		"start_date": str(doc.start_date) if doc.start_date else None,
		"end_date": str(doc.end_date) if doc.end_date else None,
		"custom_is_weekly": cint(doc.custom_is_weekly),
		"custom_week_start": str(doc.custom_week_start) if doc.custom_week_start else None,
		"custom_week_end": str(doc.custom_week_end) if doc.custom_week_end else None,
		"custom_weekly_status": doc.custom_weekly_status or WEEKLY_DRAFT,
		"custom_weekly_return_reason": doc.custom_weekly_return_reason,
		"custom_weekly_submitted_at": str(doc.custom_weekly_submitted_at)
		if doc.custom_weekly_submitted_at
		else None,
		"custom_weekly_closed_at": str(doc.custom_weekly_closed_at)
		if doc.custom_weekly_closed_at
		else None,
		"total_hours": flt(doc.total_hours, 2),
		"note": doc.note,
		"time_logs": [_serialize_row(row) for row in doc.time_logs],
		"editable_projects": editable_projects,
		"project_approvals": [
			{
				"project": row.project,
				"status": row.status,
				"return_reason": row.return_reason,
			}
			for row in doc.custom_project_approvals
		],
	}


def _blank_weekly(employee, week_start, week_end):
	return {
		"name": None,
		"employee": employee.name,
		"employee_name": employee.employee_name,
		"company": employee.company,
		"docstatus": 0,
		"start_date": str(week_start),
		"end_date": str(week_end),
		"custom_is_weekly": 1,
		"custom_week_start": str(week_start),
		"custom_week_end": str(week_end),
		"custom_weekly_status": WEEKLY_DRAFT,
		"custom_weekly_return_reason": None,
		"total_hours": 0,
		"note": None,
		"time_logs": [],
		"editable_projects": [],
		"project_approvals": [],
	}


def _release_cancelled_week_key(week_key: str):
	cancelled = frappe.get_all(
		"Timesheet",
		filters={"custom_week_key": week_key, "docstatus": 2},
		pluck="name",
	)
	for name in cancelled:
		frappe.db.set_value(
			"Timesheet",
			name,
			"custom_week_key",
			f"{week_key}|cancelled|{name}",
			update_modified=False,
		)


@frappe.whitelist()
def get_timesheet_mode(name: str):
	doc = frappe.get_doc("Timesheet", name)
	frappe.has_permission("Timesheet", "read", doc=doc, throw=True)
	return {"is_weekly": cint(getattr(doc, "custom_is_weekly", 0))}


@frappe.whitelist()
def get_weekly_timesheet(name: str | None = None, week_start: str | None = None):
	employee = _current_employee()
	if name:
		doc = frappe.get_doc("Timesheet", name)
		_assert_employee_owns(doc)
		if not cint(doc.custom_is_weekly):
			frappe.throw(_("This is a legacy daily timesheet."))
		return _serialize_weekly(doc)

	start, end = _week_bounds(week_start)
	week_key = f"{employee.name}|{start}"
	existing = frappe.db.get_value(
		"Timesheet", {"custom_week_key": week_key, "docstatus": ("<", 2)}, "name"
	)
	if existing:
		return _serialize_weekly(frappe.get_doc("Timesheet", existing))
	return _blank_weekly(employee, start, end)


@frappe.whitelist()
def get_my_timesheets(limit: int = 20):
	employee = _current_employee()
	limit = min(max(cint(limit), 1), 100)
	weekly = frappe.get_all(
		"Timesheet",
		filters={"employee": employee.name, "custom_is_weekly": 1, "docstatus": ("<", 2)},
		fields=[
			"name",
			"start_date",
			"end_date",
			"total_hours",
			"docstatus",
			"custom_weekly_status",
			"custom_weekly_return_reason",
		],
		order_by="custom_week_start desc",
		limit_page_length=100,
	)
	weekly = [
		doc
		for doc in weekly
		if doc.custom_weekly_status != WEEKLY_DRAFT or flt(doc.total_hours) > 0
	][:limit]
	legacy = frappe.get_all(
		"Timesheet",
		filters={"employee": employee.name, "custom_is_weekly": ("!=", 1)},
		fields=["name", "start_date", "end_date", "total_hours", "docstatus", "status"],
		order_by="start_date desc",
		limit_page_length=limit,
	)
	return {"weekly": weekly, "legacy": legacy, "project_approvals": get_project_approval_queue()}


def _row_payload(row):
	return {
		"doctype": "Timesheet Detail",
		"name": row.get("name") or None,
		"project": row.get("project"),
		"activity_type": row.get("activity_type") or "Unassigned",
		"description": row.get("description"),
		"from_time": row.get("from_time"),
		"to_time": row.get("to_time"),
		"hours": flt(row.get("hours"), 4),
		"is_billable": cint(row.get("is_billable", 0)),
	}


def _normalized_project_rows(rows, project):
	values = []
	for row in rows:
		row_project = row.project if hasattr(row, "project") else row.get("project")
		if row_project != project:
			continue
		get = row.get if hasattr(row, "get") else lambda key: getattr(row, key, None)
		values.append(
			(
				get("name") or "",
				str(get("from_time") or ""),
				str(get("to_time") or ""),
				flt(get("hours"), 4),
				get("activity_type") or "Unassigned",
				get("description") or "",
			)
		)
	return sorted(values)


def _validate_correction_changes(doc, new_rows):
	returned = {
		row.project for row in doc.custom_project_approvals if row.status == APPROVAL_RETURNED
	}
	if not returned:
		frappe.throw(_("No project entries are open for correction."))

	all_projects = {row.project for row in doc.time_logs}.union(
		{row.get("project") for row in new_rows}
	)
	for project in filter(None, all_projects - returned):
		if _normalized_project_rows(doc.time_logs, project) != _normalized_project_rows(new_rows, project):
			frappe.throw(
				_("Only entries returned for correction can be changed. Project {0} is locked.").format(
					frappe.bold(project)
				)
			)


@frappe.whitelist()
def save_weekly_timesheet(payload):
	payload = frappe.parse_json(payload)
	employee = _current_employee()
	start, end = _week_bounds(payload.get("custom_week_start") or payload.get("start_date"))
	week_key = f"{employee.name}|{start}"
	name = payload.get("name")

	if name:
		doc = frappe.get_doc("Timesheet", name)
		_assert_employee_owns(doc)
		if not cint(doc.custom_is_weekly):
			frappe.throw(_("Legacy timesheets cannot be converted to the weekly workflow."))
		if doc.custom_weekly_status not in ALLOWED_EMPLOYEE_STATES:
			frappe.throw(_("This weekly timesheet is locked while it is under review."))
	else:
		existing = frappe.db.get_value(
			"Timesheet", {"custom_week_key": week_key, "docstatus": ("<", 2)}, "name"
		)
		doc = frappe.get_doc("Timesheet", existing) if existing else frappe.new_doc("Timesheet")
		if existing:
			_assert_employee_owns(doc)

	new_rows = [_row_payload(row) for row in payload.get("time_logs") or []]
	if doc.name and doc.custom_weekly_status == CORRECTION_REQUIRED:
		_validate_correction_changes(doc, new_rows)

	doc.employee = employee.name
	doc.company = employee.company
	doc.start_date = start
	doc.end_date = end
	doc.custom_is_weekly = 1
	doc.custom_week_start = start
	doc.custom_week_end = end
	doc.custom_week_key = week_key
	doc.custom_weekly_status = doc.custom_weekly_status or WEEKLY_DRAFT
	doc.note = payload.get("note")
	doc.set("time_logs", new_rows)
	doc.flags.weekly_action = "employee_save"
	# Empty weekly drafts are valid while an employee edits the week. ERPNext's
	# required child-table check should still apply when the week is submitted.
	if not new_rows:
		doc.flags.ignore_mandatory = True

	if doc.is_new():
		_release_cancelled_week_key(week_key)
		doc.insert()
	else:
		doc.save()
	return _serialize_weekly(doc)


def _project_hours_map(doc) -> dict:
	"""Summed time-log hours per project (rounded to 2), for approval rows."""
	totals: dict = {}
	for row in doc.time_logs:
		if not row.project:
			continue
		totals[row.project] = totals.get(row.project, 0.0) + flt(row.hours)
	return {project: round(hours, 2) for project, hours in totals.items()}


def _refresh_approval_hours(doc) -> None:
	"""Keep each approval row's Total Hours in sync with the time logs.

	Status/workflow fields are untouched — display correctness only.
	"""
	hours_map = _project_hours_map(doc)
	for approval in doc.custom_project_approvals:
		approval.total_hours = hours_map.get(approval.project, 0.0)


def _set_project_approvals(doc):
	projects = sorted({row.project for row in doc.time_logs})
	existing = {row.project: row for row in doc.custom_project_approvals}
	hours_map = _project_hours_map(doc)

	for row in list(doc.custom_project_approvals):
		if row.project not in projects and row.status == APPROVAL_RETURNED:
			doc.remove(row)

	for project in projects:
		controller = _project_lead_user(project)
		lead_employee = _project_lead_employee(project)
		if not controller:
			# No usable Project Lead: route straight to HR review. The review
			# UI flags these sections as "No Project Lead" from the project.
			status = APPROVAL_HR
		elif lead_employee == doc.employee:
			# Self-approval is not allowed: the employee's own section skips
			# project approval and moves directly to HR review.
			status = APPROVAL_HR
		else:
			status = APPROVAL_PENDING
		if project in existing:
			approval = existing[project]
			approval.total_hours = hours_map.get(project, 0.0)
			if approval.status == APPROVAL_APPROVED:
				continue
			approval.controller = controller
			approval.status = status
			approval.reviewed_by = None
			approval.reviewed_at = None
			approval.return_reason = None
		else:
			doc.append(
				"custom_project_approvals",
				{
					"project": project,
					"controller": controller,
					"status": status,
					"total_hours": hours_map.get(project, 0.0),
				},
			)


@frappe.whitelist()
def submit_weekly_timesheet(name: str):
	doc = frappe.get_doc("Timesheet", name)
	_assert_employee_owns(doc)
	if not cint(doc.custom_is_weekly) or doc.docstatus != 0:
		frappe.throw(_("Only an open weekly timesheet can be submitted."))
	if doc.custom_weekly_status not in ALLOWED_EMPLOYEE_STATES:
		frappe.throw(_("This weekly timesheet has already been submitted."))
	if not doc.time_logs:
		frappe.throw(_("Add at least one time entry before submitting the week."))

	_set_project_approvals(doc)
	statuses = {row.status for row in doc.custom_project_approvals}
	doc.custom_weekly_status = PENDING_PROJECT if APPROVAL_PENDING in statuses else PENDING_HR
	doc.custom_weekly_submitted_at = doc.custom_weekly_submitted_at or now_datetime()
	doc.custom_weekly_return_reason = None
	doc.flags.weekly_action = "employee_submit"
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", _("Weekly timesheet submitted for approval."))

	pending_approvals = [
		row for row in doc.custom_project_approvals if row.status == APPROVAL_PENDING
	]
	if pending_approvals:
		for approval in pending_approvals:
			_notify_project_report(approval.controller, approval.project, doc.custom_week_start)
	else:
		_notify(
			_hr_users(),
			_("Weekly timesheet is ready for HR review"),
			_("{0}'s weekly timesheet is ready for final review.").format(doc.employee_name),
			doc.name,
		)
	return _serialize_weekly(doc)


@frappe.whitelist()
def get_project_approval_queue():
	approvals = frappe.get_all(
		"Timesheet Project Approval",
		filters={
			"controller": frappe.session.user,
			"status": ("in", [APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_RETURNED, APPROVAL_HR]),
		},
		fields=["name", "parent", "project", "status"],
		order_by="creation asc",
		limit_page_length=1000,
	)
	documents = {}
	groups = {}
	pending_groups = set()
	for approval in approvals:
		if approval.parent not in documents:
			documents[approval.parent] = frappe.get_doc("Timesheet", approval.parent)
		doc = documents[approval.parent]
		if doc.docstatus != 0 or not doc.custom_weekly_submitted_at:
			continue
		key = (approval.project, str(doc.custom_week_start), str(doc.custom_week_end))
		groups.setdefault(key, []).append((approval, doc))
		if approval.status == APPROVAL_PENDING and doc.custom_weekly_status == PENDING_PROJECT:
			pending_groups.add(key)

	result = []
	for key in sorted(pending_groups, key=lambda item: (item[1], item[0]), reverse=True):
		project, week_start, week_end = key
		dates = [add_days(getdate(week_start), offset) for offset in range(7)]
		members = []
		for approval, doc in groups[key]:
			daily_hours = {str(day): 0.0 for day in dates}
			for row in doc.time_logs:
				if row.project != project or not row.from_time:
					continue
				entry_date = str(get_datetime(row.from_time).date())
				if entry_date in daily_hours:
					daily_hours[entry_date] += flt(row.hours)
			members.append(
				{
					"approval_name": approval.name,
					"employee_name": doc.employee_name,
					"status": approval.status,
					"daily_hours": [round(daily_hours[str(day)], 2) for day in dates],
					"weekly_total": round(sum(daily_hours.values()), 2),
				}
			)
		result.append(
			{
				"name": f"{project}|{week_start}",
				"project": project,
				"week_start": week_start,
				"week_end": week_end,
				"days": [str(day) for day in dates],
				"members": sorted(members, key=lambda member: member["employee_name"]),
			}
		)
	return result


def _review_project_approval_row(approval, action: str, reason: str | None = None):
	if approval.controller != frappe.session.user:
		frappe.throw(_("You are not the Project Lead for this project."), frappe.PermissionError)
	if approval.status != APPROVAL_PENDING:
		frappe.throw(_("This project review has already been completed."))

	doc = frappe.get_doc("Timesheet", approval.parent)
	row = next(item for item in doc.custom_project_approvals if item.name == approval.name)
	row.reviewed_by = frappe.session.user
	row.reviewed_at = now_datetime()
	row.return_reason = (reason or "").strip() or None
	row.status = APPROVAL_APPROVED if action == "approve" else APPROVAL_RETURNED

	if action == "return":
		doc.custom_weekly_status = CORRECTION_REQUIRED
		doc.custom_weekly_return_reason = row.return_reason
	else:
		statuses = {item.status for item in doc.custom_project_approvals}
		if not statuses.intersection({APPROVAL_PENDING, APPROVAL_RETURNED}):
			doc.custom_weekly_status = PENDING_HR
			doc.custom_weekly_return_reason = None

	doc.flags.weekly_action = "project_lead_review"
	doc.save(ignore_permissions=True)
	doc.add_comment(
		"Comment",
		_("Project {0} was {1} by Project Lead {2}.").format(
			approval.project, _("approved") if action == "approve" else _("returned"), frappe.session.user
		),
	)

	if action == "return":
		_notify(
			[_employee_user(doc.employee)],
			_("Weekly timesheet needs correction"),
			_("Project {0} was returned: {1}").format(approval.project, row.return_reason),
			doc.name,
		)
	elif doc.custom_weekly_status == PENDING_HR:
		_notify(
			_hr_users(),
			_("Weekly timesheet is ready for HR review"),
			_("{0}'s weekly timesheet is ready for final review.").format(doc.employee_name),
			doc.name,
		)
	return doc


@frappe.whitelist()
def approve_project_week(project: str, week_start: str):
	pending = frappe.get_all(
		"Timesheet Project Approval",
		filters={"controller": frappe.session.user, "project": project, "status": APPROVAL_PENDING},
		fields=["name", "parent", "project", "controller", "status"],
		limit_page_length=1000,
	)
	matching = []
	for approval in pending:
		doc = frappe.get_doc("Timesheet", approval.parent)
		if doc.docstatus == 0 and str(doc.custom_week_start) == str(getdate(week_start)):
			matching.append(approval)
	if not matching:
		frappe.throw(_("No pending rows were found for this project report."))
	for approval in matching:
		_review_project_approval_row(approval, "approve")
	return {"approved": len(matching)}


@frappe.whitelist()
def review_project_approval(approval_name: str, action: str, reason: str | None = None):
	if action not in {"approve", "return"}:
		frappe.throw(_("Invalid review action."))
	if action == "return" and not (reason or "").strip():
		frappe.throw(_("A return reason is required."))

	approval = frappe.get_doc("Timesheet Project Approval", approval_name)
	if action == "approve":
		doc = frappe.get_doc("Timesheet", approval.parent)
		return approve_project_week(approval.project, doc.custom_week_start)

	doc = _review_project_approval_row(approval, action, reason)
	return {"status": doc.custom_weekly_status}


@frappe.whitelist()
def approve_project_review(approval_name: str):
	"""Approve a single project review section (Project Lead only)."""
	approval = frappe.get_doc("Timesheet Project Approval", approval_name)
	doc = _review_project_approval_row(approval, "approve")
	return {"status": doc.custom_weekly_status}


def _lead_scoped_projects(user: str | None = None) -> tuple[set, str | None]:
	"""Open projects led by the user's employee. Returns (project names, employee)."""
	employee = frappe.db.get_value(
		"Employee", {"user_id": user or frappe.session.user, "status": "Active"}, "name"
	)
	if not employee:
		return set(), None
	rows = frappe.db.get_all(
		"Project",
		filters={"custom_project_lead": employee, "status": "Open"},
		pluck="name",
	)
	return set(rows), employee


@frappe.whitelist()
def get_project_review_queue():
	"""Review sections for the current Project Lead (all sections for HR).

	One row per employee/project/week. Server-enforced scoping: Project Leads
	see only projects they lead; everyone else sees an empty list.
	"""
	lead_projects, employee = _lead_scoped_projects()
	hr = _is_hr()
	if not hr and not lead_projects:
		return []

	approvals = frappe.get_all(
		"Timesheet Project Approval",
		filters={
			"status": ("in", [APPROVAL_PENDING, APPROVAL_RETURNED, APPROVAL_APPROVED, APPROVAL_HR])
		},
		fields=[
			"name",
			"parent",
			"project",
			"status",
			"controller",
			"reviewed_by",
			"reviewed_at",
			"return_reason",
		],
		order_by="creation asc",
		limit_page_length=2000,
	)
	parents = {a.parent for a in approvals}
	docs = {}
	for parent in parents:
		try:
			docs[parent] = frappe.get_doc("Timesheet", parent)
		except frappe.DoesNotExistError:
			continue

	project_leads = {}
	names = {a.project for a in approvals}
	if names:
		for row in frappe.db.get_all(
			"Project", filters={"name": ("in", list(names))}, fields=["name", "project_name", "custom_project_lead"]
		):
			project_leads[row.name] = row

	result = []
	for approval in approvals:
		doc = docs.get(approval.parent)
		if doc is None or doc.docstatus != 0 or not doc.custom_weekly_submitted_at:
			continue
		if not hr and approval.project not in lead_projects:
			continue
		rows = [
			row
			for row in doc.time_logs
			if row.project == approval.project and row.from_time
		]
		if not rows:
			continue
		hours = round(sum(flt(row.hours) for row in rows), 2)
		lead_employee = (project_leads.get(approval.project) or {}).get("custom_project_lead")
		if approval.status == APPROVAL_HR and lead_employee == doc.employee:
			route_reason = "self"
		elif approval.status == APPROVAL_HR and not lead_employee:
			route_reason = "no_lead"
		else:
			route_reason = None
		proj = project_leads.get(approval.project) or {}
		result.append(
			{
				"approval_name": approval.name,
				"project": approval.project,
				"project_label": proj.get("project_name") or approval.project,
				"week_start": str(doc.custom_week_start),
				"week_end": str(doc.custom_week_end),
				"employee": doc.employee,
				"employee_name": doc.employee_name,
				"hours": hours,
				"log_count": len(rows),
				"project_status": approval.status,
				"hr_status": doc.custom_weekly_status,
				"return_reason": approval.return_reason,
				"reviewed_by": approval.reviewed_by,
				"reviewed_at": str(approval.reviewed_at) if approval.reviewed_at else None,
				"submitted_at": str(doc.custom_weekly_submitted_at),
				"modified": str(doc.modified),
				"actionable": approval.status == APPROVAL_PENDING,
				"routed_to_hr_reason": route_reason,
			}
		)
	result.sort(key=lambda r: (r["week_start"], r["project"], r["employee_name"]), reverse=True)

	# Draft weeks have no approval rows yet: derive sections from time logs so
	# leads can already review them (read-only, no actions until submitted).
	parents_with_approvals = {a.parent for a in approvals}
	draft_docs = frappe.get_all(
		"Timesheet",
		filters={
			"custom_is_weekly": 1,
			"docstatus": 0,
			"custom_weekly_status": WEEKLY_DRAFT,
		},
		fields=[
			"name",
			"employee",
			"employee_name",
			"custom_week_start",
			"custom_week_end",
			"custom_weekly_status",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=500,
	)
	draft_docs = [d for d in draft_docs if d.name not in parents_with_approvals]
	if draft_docs:
		if hr:
			scoped_projects = None
		else:
			scoped_projects = lead_projects
		detail_rows = frappe.db.get_all(
			"Timesheet Detail",
			filters={"parent": ("in", [d.name for d in draft_docs])},
			fields=["parent", "project", "hours", "from_time"],
		)
		docs_by_name = {d.name: d for d in draft_docs}
		proj_names = {r.project for r in detail_rows if r.project}
		proj_labels = {}
		if proj_names:
			for p in frappe.db.get_all(
				"Project", filters={"name": ("in", list(proj_names))}, fields=["name", "project_name"]
			):
				proj_labels[p.name] = p.project_name or p.name
		grouped = {}
		for row in detail_rows:
			if not row.project or not row.from_time:
				continue
			if scoped_projects is not None and row.project not in scoped_projects:
				continue
			doc = docs_by_name.get(row.parent)
			if doc is None:
				continue
			key = (row.project, str(doc.custom_week_start), doc.employee)
			grouped.setdefault(key, {"doc": doc, "hours": 0.0, "count": 0})
			grouped[key]["hours"] += flt(row.hours)
			grouped[key]["count"] += 1
		for (project, week_start, _employee), group in grouped.items():
			doc = group["doc"]
			result.append(
				{
					"approval_name": None,
					"project": project,
					"project_label": proj_labels.get(project, project),
					"week_start": str(doc.custom_week_start),
					"week_end": str(doc.custom_week_end),
					"employee": doc.employee,
					"employee_name": doc.employee_name,
					"hours": round(group["hours"], 2),
					"log_count": group["count"],
					"project_status": WEEKLY_DRAFT,
					"hr_status": doc.custom_weekly_status,
					"return_reason": None,
					"reviewed_by": None,
					"reviewed_at": None,
					"submitted_at": None,
					"modified": str(doc.modified),
					"actionable": False,
					"routed_to_hr_reason": None,
				}
			)
	result.sort(key=lambda r: (r["week_start"], r["project"], r["employee_name"]), reverse=True)
	return result


@frappe.whitelist()
def get_project_review_detail(project: str, week_start: str, employee: str):
	"""Time logs for one employee/project/week. Project Lead of the project
	(or HR) only — enforced server-side."""
	lead_projects, _ = _lead_scoped_projects()
	if not _is_hr() and project not in lead_projects:
		frappe.throw(_("You are not the Project Lead for this project."), frappe.PermissionError)
	week_key = f"{employee}|{getdate(week_start)}"
	name = frappe.db.get_value(
		"Timesheet", {"custom_week_key": week_key, "docstatus": ("<", 2)}, "name"
	)
	if not name:
		frappe.throw(_("Weekly timesheet not found."))
	doc = frappe.get_doc("Timesheet", name)
	approval = next(
		(item for item in doc.custom_project_approvals if item.project == project), None
	)
	logs = []
	for row in sorted(doc.time_logs, key=lambda r: str(r.from_time or "")):
		if row.project != project or not row.from_time:
			continue
		logs.append(
			{
				"date": str(get_datetime(row.from_time).date()),
				"from_time": str(row.from_time)[11:16],
				"to_time": str(row.to_time)[11:16] if row.to_time else "",
				"duration": round(flt(row.hours), 2),
				"project": row.project,
				"activity_type": row.activity_type,
				"description": row.description,
			}
		)
	return {
		"project": project,
		"week_start": str(doc.custom_week_start),
		"week_end": str(doc.custom_week_end),
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"hr_status": doc.custom_weekly_status,
		"project_status": approval.status if approval else WEEKLY_DRAFT,
		"approval_name": approval.name if approval else None,
		"return_reason": approval.return_reason if approval else None,
		"actionable": bool(approval) and approval.status == APPROVAL_PENDING,
		"logs": logs,
	}


@frappe.whitelist()
def hr_return_weekly_timesheet(name: str, reason: str):
	_require_hr()
	if not (reason or "").strip():
		frappe.throw(_("A return reason is required."))

	doc = frappe.get_doc("Timesheet", name)
	if not cint(doc.custom_is_weekly) or doc.custom_weekly_status != PENDING_HR:
		frappe.throw(_("This weekly timesheet is not ready for HR review."))

	for row in doc.custom_project_approvals:
		row.status = APPROVAL_RETURNED
		row.return_reason = reason.strip()
		row.reviewed_by = frappe.session.user
		row.reviewed_at = now_datetime()
	doc.custom_weekly_status = CORRECTION_REQUIRED
	doc.custom_weekly_return_reason = reason.strip()
	doc.flags.weekly_action = "hr_return"
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", _("HR returned the weekly timesheet: {0}").format(reason.strip()))
	_notify(
		[_employee_user(doc.employee)],
		_("Weekly timesheet needs correction"),
		reason.strip(),
		doc.name,
	)
	return _serialize_weekly(doc)


@frappe.whitelist()
def hr_close_weekly_timesheet(name: str):
	_require_hr()
	doc = frappe.get_doc("Timesheet", name)
	if not cint(doc.custom_is_weekly) or doc.custom_weekly_status != PENDING_HR:
		frappe.throw(_("This weekly timesheet is not ready for HR review."))

	for row in doc.custom_project_approvals:
		if row.status == APPROVAL_HR:
			row.status = APPROVAL_APPROVED
			row.reviewed_by = frappe.session.user
			row.reviewed_at = now_datetime()
	doc.custom_weekly_status = CLOSED
	doc.custom_weekly_closed_at = now_datetime()
	doc.custom_weekly_return_reason = None
	doc.flags.weekly_action = "hr_close"
	doc.save(ignore_permissions=True)
	doc.flags.weekly_action = "hr_close"
	doc.submit()
	doc.add_comment("Comment", _("Weekly timesheet closed by HR."))
	_notify(
		[_employee_user(doc.employee)],
		_("Weekly timesheet approved"),
		_("Your weekly timesheet has been reviewed and closed by HR."),
		doc.name,
	)
	return _serialize_weekly(doc)


def _trunc_minute(value):
	"""Truncate a datetime to minute precision for overlap comparison.

	Best practice: entries are displayed and entered at HH:MM precision, so
	second-level jitter (e.g. a timer stopping at 11:00:37 against a manual
	11:00 start) must not count as an overlap. Back-to-back entries like
	10:00–11:00 and 11:00–12:00 always pass; genuine minute-level overlaps
	still fail.
	"""
	try:
		return value.replace(second=0, microsecond=0)
	except Exception:
		return value


def _validate_time_rows(doc):
	if not doc.time_logs:
		return
	week_start = getdate(doc.custom_week_start)
	week_end = getdate(doc.custom_week_end)
	week_start_dt = datetime.combine(week_start, time.min)
	week_end_exclusive = datetime.combine(add_days(week_end, 1), time.min)

	intervals = []
	for row in doc.time_logs:
		if not row.project:
			frappe.throw(_("Row {0}: Project is required.").format(row.idx))
		if frappe.db.get_value("Project", row.project, "status") != "Open":
			frappe.throw(_("Row {0}: Project must be open.").format(row.idx))
		if not row.activity_type:
			row.activity_type = "Unassigned"
		if not row.from_time or not row.to_time:
			frappe.throw(_("Row {0}: Start and end time are required.").format(row.idx))
		from_time = get_datetime(row.from_time)
		to_time = get_datetime(row.to_time)
		if from_time < week_start_dt or from_time >= week_end_exclusive:
			frappe.throw(_("Row {0}: Start time must be inside the selected week.").format(row.idx))
		if to_time <= from_time:
			frappe.throw(_("Row {0}: End time must be after start time.").format(row.idx))
		if to_time > week_end_exclusive:
			frappe.throw(_("Row {0}: End time must be inside the selected week.").format(row.idx))
		intervals.append((_trunc_minute(from_time), _trunc_minute(to_time), row.idx, row.project or ""))

	conflicts = []
	ordered = sorted(intervals)
	for previous, current in zip(ordered, ordered[1:]):
		if current[0] < previous[1]:
			conflicts.append((previous, current))
	if conflicts:
		parts = []
		for (from_1, to_1, idx_1, proj_1), (from_2, to_2, idx_2, proj_2) in conflicts[:3]:
			parts.append(
				_("{0} {1}–{2} with {3} {4}–{5} (rows {6} and {7})").format(
					proj_1 or _("entry"),
					from_1.strftime("%H:%M"),
					to_1.strftime("%H:%M"),
					proj_2 or _("entry"),
					from_2.strftime("%H:%M"),
					to_2.strftime("%H:%M"),
					idx_1,
					idx_2,
				)
			)
		extra = "" if len(conflicts) <= 3 else _(" (and {0} more)").format(len(conflicts) - 3)
		frappe.throw(_("Time entries cannot overlap: {0}.{1}").format("; ".join(parts), extra))


def prepare_weekly_document(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)):
		return
	for row in doc.time_logs:
		row.activity_type = row.activity_type or "Unassigned"


def validate_weekly_document(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)):
		return
	if not doc.custom_weekly_status:
		doc.custom_weekly_status = WEEKLY_DRAFT
	_refresh_approval_hours(doc)
	start, end = _week_bounds(doc.custom_week_start or doc.start_date)
	if getdate(doc.custom_week_start) != start or getdate(doc.custom_week_end) != end:
		frappe.throw(_("Weekly timesheets must run from Sunday through Saturday."))
	doc.start_date = start
	doc.end_date = end
	doc.custom_week_key = f"{doc.employee}|{start}"

	if not doc.is_new():
		old = doc.get_doc_before_save()
		action = doc.flags.get("weekly_action")
		if old and old.custom_weekly_status != doc.custom_weekly_status and not action:
			frappe.throw(_("Weekly approval status can only be changed through workflow actions."))
		if old and old.custom_weekly_status not in ALLOWED_EMPLOYEE_STATES and not action:
			frappe.throw(_("This weekly timesheet is locked while it is under review."))

	duplicate = frappe.db.exists(
		"Timesheet",
		{
			"custom_week_key": doc.custom_week_key,
			"docstatus": ("<", 2),
			"name": ("!=", doc.name or "New Timesheet"),
		},
	)
	if duplicate:
		frappe.throw(_("Only one weekly timesheet is allowed per employee and week."))
	_validate_time_rows(doc)


def before_weekly_submit(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)):
		return
	if doc.flags.get("weekly_action") != "hr_close" or not _is_hr():
		frappe.throw(_("Only HR can close a fully approved weekly timesheet."), frappe.PermissionError)
	if doc.custom_weekly_status != CLOSED:
		frappe.throw(_("Weekly timesheet must be in Closed status before final submission."))


def before_weekly_cancel(doc):
	if cint(getattr(doc, "custom_is_weekly", 0)):
		frappe.throw(_("Closed weekly timesheets cannot be cancelled directly."))


def before_weekly_update_after_submit(doc):
	if cint(getattr(doc, "custom_is_weekly", 0)):
		frappe.throw(_("Closed weekly timesheets cannot be edited directly."))


def save_weekly_timer_log(
	employee: str,
	from_time: str,
	to_time: str,
	project: str,
	activity_type: str | None = None,
	description: str | None = None,
) -> str:
	current_employee = _current_employee()
	if current_employee.name != employee:
		frappe.throw(_("You can only track time for yourself."), frappe.PermissionError)
	if not project:
		frappe.throw(_("Project is required before starting the timer."))

	cursor = get_datetime(from_time)
	end_time = get_datetime(to_time)
	if end_time <= cursor:
		frappe.throw(_("Timer end time must be after its start time."))

	last_name = None
	while cursor < end_time:
		week_start, week_end = _week_bounds(cursor.date())
		boundary = datetime.combine(add_days(week_end, 1), time.min)
		segment_end = min(end_time, boundary)
		week_key = f"{employee}|{week_start}"
		duplicate = frappe.db.sql(
			"""SELECT ts.name FROM `tabTimesheet` ts
			INNER JOIN `tabTimesheet Detail` detail ON detail.parent = ts.name
			WHERE ts.employee = %s AND ts.custom_week_key = %s
			AND detail.project = %s AND detail.from_time = %s AND detail.to_time = %s
			AND ts.docstatus < 2 LIMIT 1""",
			(employee, week_key, project, cursor, segment_end), as_dict=False,
		)
		if duplicate:
			last_name = duplicate[0][0]
			cursor = segment_end
			continue
		name = frappe.db.get_value(
			"Timesheet", {"custom_week_key": week_key, "docstatus": ("<", 2)}, "name"
		)
		doc = frappe.get_doc("Timesheet", name) if name else frappe.new_doc("Timesheet")
		if name:
			_assert_employee_owns(doc)
			if doc.custom_weekly_status not in ALLOWED_EMPLOYEE_STATES:
				frappe.throw(_("The weekly timesheet for {0} is locked.").format(week_start))
			if doc.custom_weekly_status == CORRECTION_REQUIRED:
				editable = {
					row.project
					for row in doc.custom_project_approvals
					if row.status == APPROVAL_RETURNED
				}
				if project not in editable:
					frappe.throw(_("This project is not open for correction."))
		else:
			doc.employee = employee
			doc.company = current_employee.company
			doc.custom_is_weekly = 1
			doc.custom_week_start = week_start
			doc.custom_week_end = week_end
			doc.custom_week_key = week_key
			doc.custom_weekly_status = WEEKLY_DRAFT

		doc.append(
			"time_logs",
			{
				"project": project,
				"activity_type": activity_type or "Unassigned",
				"description": description,
				"from_time": cursor,
				"to_time": segment_end,
				"hours": (segment_end - cursor).total_seconds() / 3600,
				"is_billable": 0,
			},
		)
		doc.flags.weekly_action = "employee_save"
		if doc.is_new():
			_release_cancelled_week_key(week_key)
			doc.insert()
		else:
			doc.save()
		last_name = doc.name
		cursor = segment_end

	return last_name
