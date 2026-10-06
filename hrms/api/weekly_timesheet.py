from __future__ import annotations

from datetime import datetime, time
import hashlib
import json

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

HR_ROLES = {"HR Manager", "HR User", "System Manager", "Company Desk Administrator"}
COMPANY_DIRECTOR_ROLE = "Company Desk Administrator"
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
	user = user or frappe.session.user
	return user == "Administrator" or bool(HR_ROLES.intersection(frappe.get_roles(user)))


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
	if COMPANY_DIRECTOR_ROLE in set(frappe.get_roles(user)):
		return True
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
	if COMPANY_DIRECTOR_ROLE in set(frappe.get_roles(user)):
		return True
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
		"return_reason": row.get("custom_return_reason"),
	}


def _serialize_weekly(doc):
	_refresh_review_routing(doc)
	editable_projects, editable_entries = [], []
	if doc.custom_weekly_status == CORRECTION_REQUIRED:
		scope = _correction_scope(doc)
		editable_projects, editable_entries = scope["projects"], scope["entries"]

	team_review_tasks = _pending_team_reviews(doc)
	return {
		"name": doc.name,
		"modified": str(doc.modified) if doc.modified else None,
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
		"overlap_warnings": weekly_overlap_warnings(doc),
		"note": doc.note,
		"time_logs": [_serialize_row(row) for row in doc.time_logs],
		"editable_projects": editable_projects,
		"editable_entries": editable_entries,
		"team_review_tasks": team_review_tasks,
		# Kept for older clients; these are tasks, never approval gates.
		"team_review_blockers": team_review_tasks,
		"ready_for_hr_close": doc.docstatus == 0 and doc.custom_weekly_status == PENDING_HR
			and _project_reviews_ready(doc),
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
	scope = _correction_scope(doc)
	old_rows = {row.name: row for row in doc.time_logs}
	names = [row.get("name") for row in new_rows if row.get("name")]
	if len(names) != len(set(names)):
		frappe.throw(_("Duplicate time entry identifiers are not allowed."))
	new_by_name = {row.get("name"): row for row in new_rows if row.get("name")}
	for name, old in old_rows.items():
		if name in scope["entries"] or old.project in scope["projects"]:
			continue
		new = new_by_name.get(name)
		if not new or _entry_signature(old) != _entry_signature(new):
			frappe.throw(_("Only the time entries returned for correction can be changed."))
	for row in new_rows:
		if row.get("name") and row["name"] not in old_rows:
			frappe.throw(_("Unknown time entry identifier."))
		if not row.get("name") and row.get("project") not in scope["projects"]:
			frappe.throw(_("New entries can only be added to a fully returned project section."))


def _entry_signature(row):
	return (
		row.get("project"), str(row.get("from_time") or ""), str(row.get("to_time") or ""),
		flt(row.get("hours"), 4), row.get("activity_type") or "Unassigned",
		row.get("description") or "", cint(row.get("is_billable")),
	)


def _correction_scope(doc):
	value = doc.get("custom_correction_scope")
	if value:
		return frappe.parse_json(value)
	# Existing returns predate per-entry corrections and retain their full project scope.
	return {
		"entries": [],
		"projects": [row.project for row in doc.custom_project_approvals if row.status == APPROVAL_RETURNED],
	}


def _mark_correction(doc, rows, reason, projects=()):
	scope = _correction_scope(doc) if doc.custom_weekly_status == CORRECTION_REQUIRED else {"entries": [], "projects": []}
	scope["entries"] = sorted(set(scope["entries"]) | {row.name for row in rows})
	scope["projects"] = sorted(set(scope["projects"]) | set(projects))
	doc.custom_correction_scope = frappe.as_json(scope)
	for row in rows:
		row.custom_return_reason = reason
	doc.custom_weekly_status = CORRECTION_REQUIRED
	doc.custom_weekly_return_reason = reason


def _legacy_draft_is_additive(doc, payload):
	"""Accept versionless clients only when every persisted value is preserved.

	A cached pre-version frontend can append entries, but cannot overwrite,
	delete, or resurrect a server entry without first fetching its version.
	"""
	if (payload.get("note") or "") != (doc.note or ""):
		return False
	if not payload.get("name") or payload.get("name") != doc.name:
		return False
	server_rows = {row.name: _serialize_row(row) for row in doc.time_logs}
	seen = set()
	for row in payload.get("time_logs") or []:
		name = row.get("name")
		if not name:
			continue
		if name in seen or name not in server_rows:
			return False
		seen.add(name)
		server = server_rows[name]
		for field in ("project", "activity_type", "description"):
			if (row.get(field) or "") != (server.get(field) or ""):
				return False
		for field in ("from_time", "to_time"):
			if not row.get(field) or get_datetime(row[field]) != get_datetime(server[field]):
				return False
		if flt(row.get("hours"), 4) != server["hours"] or cint(row.get("is_billable")) != server["is_billable"]:
			return False
	return seen == set(server_rows)


@frappe.whitelist()
def save_weekly_timesheet(payload, expected_modified=None):
	payload = frappe.parse_json(payload)
	from hrms.utils.account_lock import lock_current_account
	lock_current_account()
	employee = _current_employee()
	start, end = _week_bounds(payload.get("custom_week_start") or payload.get("start_date"))
	week_key = f"{employee.name}|{start}"
	name = payload.get("name")

	if name:
		frappe.db.sql("SELECT name FROM tabTimesheet WHERE name = %s FOR UPDATE", (name,))
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
	if doc.docstatus != 0 or (not doc.is_new() and doc.custom_weekly_status not in ALLOWED_EMPLOYEE_STATES):
		frappe.throw(_("This weekly timesheet is locked while it is under review."))
	client_modified = expected_modified or payload.get("modified")
	if not doc.is_new() and str(client_modified or "") != str(doc.modified) and not (
		not client_modified and _legacy_draft_is_additive(doc, payload)
	):
		frappe.local.response.http_status_code = 409
		frappe.throw(_("This week changed elsewhere. Your draft is preserved; review the latest version before saving."), frappe.TimestampMismatchError)

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
	return_reasons = {row.name: row.get("custom_return_reason") for row in doc.time_logs}
	doc.set("time_logs", new_rows)
	for row in doc.time_logs:
		row.custom_return_reason = return_reasons.get(row.name)
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


def _entry_revision(row):
	"""Approval covers the saved business values, not a mutable row identifier."""
	values = [row.project, row.activity_type or "Unassigned", row.description or "",
		str(get_datetime(row.from_time)), str(get_datetime(row.to_time)),
		round(flt(row.hours), 4), cint(row.is_billable)]
	return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def _entry_reviews(doc, approval):
	if not approval:
		return {}
	if approval.get("entry_reviews"):
		return frappe.parse_json(approval.entry_reviews)
	# Existing approved sections retain their original evidence. On the next
	# write it is captured against the BEFORE image, never against edited rows.
	if approval.status == APPROVAL_APPROVED:
		return {row.name: {"revision": _entry_revision(row), "reviewed_by": approval.reviewed_by,
			"reviewed_at": str(approval.reviewed_at or "")} for row in doc.time_logs if row.project == approval.project}
	return {}


def _set_project_approvals(doc):
	projects = sorted({row.project for row in doc.time_logs})
	old = doc.get_doc_before_save() if not doc.is_new() else None
	existing = {row.project: row for row in doc.custom_project_approvals}
	old_approvals = {row.project: row for row in old.custom_project_approvals} if old else {}
	for approval in list(doc.custom_project_approvals):
		if approval.project not in projects:
			doc.remove(approval)
	for project in projects:
		approval = existing.get(project)
		if not approval:
			approval = doc.append("custom_project_approvals", {"project": project, "status": APPROVAL_PENDING})
		controller = _project_lead_user(project)
		reviews = _entry_reviews(doc, approval) if approval.get("entry_reviews") else _entry_reviews(old or doc, old_approvals.get(project) or approval)
		if approval.controller != controller:
			reviews = {}
			approval.reviewed_by = None
			approval.reviewed_at = None
		logs = [row for row in doc.time_logs if row.project == project]
		reviews = {row.name: reviews[row.name] for row in logs
			if row.name in reviews and reviews[row.name].get("revision") == _entry_revision(row)}
		approval.controller = controller
		approval.entry_reviews = json.dumps(reviews)
		if not controller or _project_lead_employee(project) == doc.employee:
			approval.status = APPROVAL_HR
		elif any(row.get("custom_return_reason") for row in logs):
			approval.status = APPROVAL_RETURNED
		elif all(row.name in reviews for row in logs):
			approval.status = APPROVAL_APPROVED
		else:
			approval.status = APPROVAL_PENDING
		if approval.status != APPROVAL_RETURNED:
			approval.return_reason = None


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

	doc.custom_correction_scope = None
	for row in doc.time_logs:
		row.custom_return_reason = None
	_set_project_approvals(doc)
	doc.custom_weekly_status = PENDING_HR if _project_reviews_ready(doc) else PENDING_PROJECT
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
	elif doc.custom_weekly_status == PENDING_HR:
		_notify(
			_hr_users(),
			_("Weekly timesheet is ready for HR review"),
			_("{0}'s weekly timesheet is ready for final review.").format(doc.employee_name),
			doc.name,
		)
	return _serialize_weekly(doc)


def _refresh_review_routing(doc):
	"""Read projection of current lead assignments; never writes on GET."""
	if doc.docstatus != 0 or not cint(doc.custom_is_weekly):
		return
	_set_project_approvals(doc)
	if doc.custom_weekly_submitted_at and doc.custom_weekly_status in {PENDING_PROJECT, PENDING_HR}:
		doc.custom_weekly_status = PENDING_HR if _project_reviews_ready(doc) else PENDING_PROJECT


def refresh_project_timesheet_routing(project_doc):
	"""Re-route open reviews in the same transaction as a lead reassignment."""
	old = project_doc.get_doc_before_save()
	if not old or old.get("custom_project_lead") == project_doc.get("custom_project_lead"):
		return
	names = frappe.db.sql("""SELECT DISTINCT t.name FROM `tabTimesheet` t
		JOIN `tabTimesheet Detail` d ON d.parent=t.name AND d.parenttype='Timesheet'
		WHERE d.project=%s AND t.custom_is_weekly=1 AND t.docstatus=0 ORDER BY t.name""", project_doc.name, pluck=True)
	for name in names:
		frappe.db.sql("SELECT name FROM `tabTimesheet` WHERE name=%s FOR UPDATE", name)
		doc = frappe.get_doc("Timesheet", name)
		_refresh_review_routing(doc)
		doc.flags.weekly_action = "project_lead_review"
		doc.save(ignore_permissions=True)
		doc.add_comment("Comment", _("Project Lead changed for {0}; open review routing refreshed. Previous approvals by another lead do not apply to the new assignment.").format(project_doc.name))
		controller = _project_lead_user(project_doc.name)
		if controller and controller != _employee_user(doc.employee):
			_notify_project_report(controller, project_doc.name, doc.custom_week_start)


def _employee_has_active_account(employee):
	account = frappe.db.get_value("Employee", employee, ["status", "user_id", "docstatus"], as_dict=True)
	return bool(account and account.status == "Active" and cint(account.docstatus) < 2
		and account.user_id and cint(frappe.db.get_value("User", account.user_id, "enabled")))


def _pending_team_reviews(doc):
	projects = set(frappe.get_all("Project", filters={"custom_project_lead": doc.employee}, pluck="name"))
	if not projects or not doc.custom_week_start:
		return []
	weeks = frappe.get_all("Timesheet", filters={
		"custom_is_weekly": 1, "docstatus": 0,
		"custom_week_start": doc.custom_week_start, "employee": ("!=", doc.employee),
	}, fields=["name", "employee_name"], limit_page_length=0)
	blockers = []
	for week in weeks:
		team = frappe.get_doc("Timesheet", week.name)
		if not _employee_has_active_account(team.employee):
			continue
		logged = {row.project for row in team.time_logs}.intersection(projects)
		_set_project_approvals(team)
		approvals = {row.project: row.status for row in team.custom_project_approvals}
		for project in sorted(logged):
			if approvals.get(project) != APPROVAL_APPROVED:
				blockers.append({"employee_name": week.employee_name, "project": project,
					"status": approvals.get(project) or WEEKLY_DRAFT})
	return blockers


def _team_review_blockers(doc):
	"""Compatibility alias: pending team tasks do not block personal weeks."""
	return _pending_team_reviews(doc)


def _refresh_ready_lead_weeks(week_start, exclude, lead_employee):
	# Recover previously staged personal weeks using only their own reviews.
	# Team review tasks must never delay another person's weekly approval.
	if not lead_employee:
		return
	weeks = frappe.get_all("Timesheet", filters={
		"custom_is_weekly": 1, "docstatus": 0, "custom_week_start": week_start,
		"custom_weekly_status": PENDING_PROJECT, "name": ("!=", exclude),
		"employee": lead_employee,
	}, pluck="name", limit_page_length=0)
	for name in weeks:
		doc = frappe.get_doc("Timesheet", name)
		if not _project_reviews_ready(doc):
			continue
		doc.custom_weekly_status = PENDING_HR
		doc.flags.weekly_action = "project_lead_review"
		doc.save(ignore_permissions=True)
		doc.add_comment("Comment", _("Personal project reviews completed; ready for final HR review."))
		_notify(_hr_users(), _("Weekly timesheet is ready for HR review"),
			_("{0}'s weekly timesheet is ready for final review.").format(doc.employee_name), doc.name)


def _project_reviews_ready(doc):
	projects = {row.project for row in doc.time_logs}
	approvals = {}
	for row in doc.custom_project_approvals:
		if row.project in approvals:
			return False
		approvals[row.project] = row
	if not projects or not projects.issubset(approvals):
		return False
	for project in projects:
		row = approvals[project]
		if row.status == APPROVAL_APPROVED:
			reviews = _entry_reviews(doc, row)
			if any(reviews.get(log.name, {}).get("revision") != _entry_revision(log) for log in doc.time_logs if log.project == project):
				return False
			continue
		if row.status != APPROVAL_HR:
			return False
		# HR routing is an exception for unavailable leads or their own entries,
		# not a replacement for an assigned lead's review.
		if _project_lead_user(project) and _project_lead_employee(project) != doc.employee:
			return False
	return not any(row.status in {APPROVAL_PENDING, APPROVAL_RETURNED} for row in approvals.values())


@frappe.whitelist()
def get_project_approval_queue():
	reviewer_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
	filters = {"status": ("in", [APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_RETURNED, APPROVAL_HR])}
	if not _is_hr():
		employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
		projects = set()
		if employee:
			for field in ("custom_project_lead", "custom_project_manager"):
				projects.update(frappe.get_all("Project", filters={field: employee, "status": "Open"}, pluck="name"))
		if projects:
			filters["project"] = ("in", sorted(projects))
		else:
			filters["controller"] = frappe.session.user
	approvals = frappe.get_all(
		"Timesheet Project Approval",
		filters=filters,
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
		if doc.docstatus != 0 or not _employee_has_active_account(doc.employee):
			continue
		if reviewer_employee and doc.employee == reviewer_employee:
			continue
		key = (approval.project, str(doc.custom_week_start), str(doc.custom_week_end))
		groups.setdefault(key, []).append((approval, doc))
		if approval.status == APPROVAL_PENDING and doc.custom_weekly_status in {WEEKLY_DRAFT, PENDING_PROJECT, CORRECTION_REQUIRED}:
			pending_groups.add(key)

	result = []
	project_labels = {row.name: row.project_name for row in frappe.get_all(
		"Project", filters={"name": ("in", list({key[0] for key in pending_groups}))},
		fields=["name", "project_name"],
	)} if pending_groups else {}
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
					"employee": doc.employee,
					"status": approval.status,
					"activity_types": sorted({row.activity_type or "Unassigned" for row in doc.time_logs if row.project == project}),
					"daily_hours": [round(daily_hours[str(day)], 2) for day in dates],
					"weekly_total": round(sum(daily_hours.values()), 2),
				}
			)
		result.append(
			{
				"name": f"{project}|{week_start}",
				"project": project,
				"project_label": project_labels.get(project) or project,
				"week_start": week_start,
				"week_end": week_end,
				"days": [str(day) for day in dates],
				"members": sorted(members, key=lambda member: member["employee_name"]),
			}
		)
	return result


@frappe.whitelist(methods=["POST"])
def review_saved_project_entries(name: str, project: str, expected_modified: str, entries=None, action: str = "approve", reason: str | None = None):
	if action not in {"approve", "return"}:
		frappe.throw(_("Invalid review action."))
	if not _is_hr() and frappe.session.user not in {_project_lead_user(project), _project_manager_user(project)}:
		frappe.throw(_("You cannot review entries for this project."), frappe.PermissionError)
	frappe.db.sql("SELECT name FROM `tabTimesheet` WHERE name=%s FOR UPDATE", name)
	doc = frappe.get_doc("Timesheet", name)
	if _employee_user(doc.employee) == frappe.session.user:
		frappe.throw(_("Your own project entries require another reviewer."), frappe.PermissionError)
	if not cint(doc.custom_is_weekly) or doc.docstatus != 0 or doc.custom_weekly_status not in {WEEKLY_DRAFT, PENDING_PROJECT, CORRECTION_REQUIRED, PENDING_HR}:
		frappe.throw(_("This project review is no longer open."))
	if not expected_modified or str(doc.modified) != str(expected_modified):
		frappe.throw(_("The time entries changed. Refresh and review the latest saved entries before approving."))
	entries = frappe.parse_json(entries) if isinstance(entries, str) else entries
	if entries is not None and (not isinstance(entries, list) or not entries or any(not isinstance(item, str) for item in entries)):
		frappe.throw(_("Select saved entries belonging to this project."))
	if not _is_hr() and not _employee_has_active_account(doc.employee):
		frappe.throw(_("This employee account is inactive. The record is archived for HR follow-up."))
	logs = [row for row in doc.time_logs if row.project == project and (entries is None or row.name in entries)]
	if not logs or (entries is not None and (not isinstance(entries, list) or {row.name for row in logs} != set(entries))):
		frappe.throw(_("Select saved entries belonging to this project."))
	if action == "return" and not (reason or "").strip():
		frappe.throw(_("A return reason is required."))
	_set_project_approvals(doc)
	approval = next(row for row in doc.custom_project_approvals if row.project == project)
	reviews = _entry_reviews(doc, approval)
	for log in logs:
		if action == "approve":
			if log.get("custom_return_reason"):
				frappe.throw(_("Returned entries must be corrected before approval."))
			reviews[log.name] = {"revision": _entry_revision(log), "reviewed_by": frappe.session.user, "reviewed_at": str(now_datetime())}
		else:
			reviews.pop(log.name, None)
			log.custom_return_reason = reason.strip()
	approval.entry_reviews = json.dumps(reviews)
	approval.reviewed_by = frappe.session.user
	approval.reviewed_at = now_datetime()
	if action == "return":
		approval.return_reason = reason.strip()
	if action == "return" and doc.custom_weekly_status != WEEKLY_DRAFT:
		_mark_correction(doc, logs, reason.strip())
	_set_project_approvals(doc)
	if doc.custom_weekly_submitted_at and doc.custom_weekly_status != CORRECTION_REQUIRED:
		doc.custom_weekly_status = PENDING_HR if _project_reviews_ready(doc) else PENDING_PROJECT
	doc.flags.weekly_action = "project_lead_review"
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", _("Project {0}: {1} saved entries {2} by {3}.").format(project, len(logs), action, frappe.session.user))
	_refresh_ready_lead_weeks(doc.custom_week_start, doc.name, _project_lead_employee(project))
	if action == "return":
		_notify([_employee_user(doc.employee)], _("Time entries need correction"), reason.strip(), doc.name)
	elif doc.custom_weekly_status == PENDING_HR:
		_notify(_hr_users(), _("Weekly timesheet is ready for HR review"), doc.employee_name, doc.name)
	return {"status": doc.custom_weekly_status, "reviewed": len(logs), "modified": str(doc.modified)}


def _review_project_approval_row(approval, action: str, reason: str | None = None):
	doc = frappe.get_doc("Timesheet", approval.parent)
	review_saved_project_entries(doc.name, approval.project, str(doc.modified), action=action, reason=reason)
	return frappe.get_doc("Timesheet", doc.name)


@frappe.whitelist()
def approve_project_week(project: str, week_start: str):
	filters = {"project": project, "status": APPROVAL_PENDING}
	if not _is_hr() and _project_lead_user(project) != frappe.session.user and _project_manager_user(project) != frappe.session.user:
		filters["controller"] = frappe.session.user
	pending = frappe.get_all(
		"Timesheet Project Approval",
		filters=filters,
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
	user = user or frappe.session.user
	if COMPANY_DIRECTOR_ROLE in set(frappe.get_roles(user)):
		return set(frappe.get_all("Project", filters={"status": "Open"}, pluck="name")), None
	employee = frappe.db.get_value(
		"Employee", {"user_id": user, "status": "Active"}, "name"
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
	if employee:
		lead_projects.update(frappe.get_all("Project", filters={"custom_project_manager": employee, "status": "Open"}, pluck="name"))
	reviewer_employee = employee or frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
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
		if doc is None or doc.docstatus != 0 or not _employee_has_active_account(doc.employee):
			continue
		if reviewer_employee and doc.employee == reviewer_employee:
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
				"is_own_section": doc.employee == reviewer_employee,
				"log_count": len(rows),
				"activity_types": sorted({row.activity_type or "Unassigned" for row in rows}),
				"project_status": approval.status,
				"hr_status": doc.custom_weekly_status,
				"return_reason": approval.return_reason,
				"reviewed_by": approval.reviewed_by,
				"reviewed_at": str(approval.reviewed_at) if approval.reviewed_at else None,
				"submitted_at": str(doc.custom_weekly_submitted_at),
				"modified": str(doc.modified),
				"timesheet": doc.name,
				"actionable": _project_section_actionable(doc, approval),
				"routed_to_hr_reason": route_reason,
			}
		)
	result.sort(key=lambda r: (r["week_start"], r["project"], r["employee_name"]), reverse=True)

	# Draft weeks have no approval rows yet: derive sections from time logs so
	# leads can review saved entries and request corrections before submission.
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
	draft_docs = [d for d in draft_docs if d.name not in parents_with_approvals and d.employee != reviewer_employee and _employee_has_active_account(d.employee)]
	if draft_docs:
		if hr:
			scoped_projects = None
		else:
			scoped_projects = lead_projects
		detail_rows = frappe.db.get_all(
			"Timesheet Detail",
			filters={"parent": ("in", [d.name for d in draft_docs])},
			fields=["parent", "project", "hours", "from_time", "activity_type"],
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
			grouped.setdefault(key, {"doc": doc, "hours": 0.0, "count": 0, "activities": set()})
			grouped[key]["hours"] += flt(row.hours)
			grouped[key]["count"] += 1
			grouped[key]["activities"].add(row.activity_type or "Unassigned")
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
					"is_own_section": doc.employee == reviewer_employee,
					"log_count": group["count"],
					"activity_types": sorted(group["activities"]),
					"project_status": WEEKLY_DRAFT,
					"hr_status": doc.custom_weekly_status,
					"return_reason": None,
					"reviewed_by": None,
					"reviewed_at": None,
					"submitted_at": None,
					"modified": str(doc.modified),
					"timesheet": doc.name,
					"actionable": True,
					"routed_to_hr_reason": None,
				}
			)
	result.sort(key=lambda r: (r["modified"], r["week_start"], r["project"], r["employee_name"]), reverse=True)
	return result


@frappe.whitelist()
def get_team_timesheet_sections(view="current", cursor=None, filters=None):
	from hrms.api.team_timesheets import get_sections
	return get_sections(view, cursor, filters)


def _project_section_actionable(doc, approval):
	return bool(doc.docstatus == 0
		and doc.custom_weekly_status in {WEEKLY_DRAFT, PENDING_PROJECT, CORRECTION_REQUIRED}
		and (not approval or approval.status == APPROVAL_PENDING))


def _project_section_review_hint(doc, approval):
	if doc.docstatus == 1 or doc.custom_weekly_status == CLOSED:
		return _("This week is final and read-only.")
	status = approval.status if approval else WEEKLY_DRAFT
	if status == APPROVAL_RETURNED:
		return _("Returned entries must be corrected before approval. The employee still needs to submit the complete week.")
	if status == APPROVAL_APPROVED:
		return _("This saved project section is approved. Changes require another review; final approval is by HR after submission.")
	if status == APPROVAL_HR:
		return _("This section is routed to HR for final review.")
	return _("Review saved entries now. Approval covers this version only; later changes require another review. The employee still submits the complete week.")


@frappe.whitelist()
def get_project_review_detail(project: str, week_start: str, employee: str):
	"""Time logs for one employee/project/week. Project Lead of the project
	(or HR) only — enforced server-side."""
	if not _is_hr() and _project_lead_user(project) != frappe.session.user and _project_manager_user(project) != frappe.session.user:
		frappe.throw(_("You are not the Project Lead for this project."), frappe.PermissionError)
	week_key = f"{employee}|{getdate(week_start)}"
	name = frappe.db.get_value(
		"Timesheet", {"custom_week_key": week_key, "docstatus": ("<", 2)}, "name"
	)
	if not name:
		frappe.throw(_("Weekly timesheet not found."))
	doc = frappe.get_doc("Timesheet", name)
	_refresh_review_routing(doc)
	approval = next(
		(item for item in doc.custom_project_approvals if item.project == project), None
	)
	logs = []
	for row in sorted(doc.time_logs, key=lambda r: str(r.from_time or "")):
		if row.project != project or not row.from_time:
			continue
		logs.append(
			{
				"name": row.name,
				"date": str(get_datetime(row.from_time).date()),
				"from_time": str(row.from_time)[11:16],
				"to_time": str(row.to_time)[11:16] if row.to_time else "",
				"duration": round(flt(row.hours), 2),
				"project": row.project,
				"activity_type": row.activity_type,
				"description": row.description,
				"return_reason": row.get("custom_return_reason"),
				"approved": _entry_reviews(doc, approval).get(row.name, {}).get("revision") == _entry_revision(row),
			}
		)
	active_employee = _employee_has_active_account(doc.employee)
	open_project_review = not approval or approval.status not in {APPROVAL_APPROVED, APPROVAL_HR}
	return {
		"timesheet": doc.name,
		"modified": str(doc.modified),
		"project": project,
		"week_start": str(doc.custom_week_start),
		"week_end": str(doc.custom_week_end),
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"hr_status": doc.custom_weekly_status,
		"project_status": approval.status if approval else WEEKLY_DRAFT,
		"approval_name": approval.name if approval else None,
		"return_reason": approval.return_reason if approval else None,
		"actionable": active_employee and _project_section_actionable(doc, approval),
		"selection_reason": _project_section_review_hint(doc, approval) if active_employee else _("Employee account is inactive. This record is archived for HR follow-up."),
		"can_review_entries": active_employee and open_project_review and doc.docstatus == 0 and doc.custom_weekly_status in {WEEKLY_DRAFT, PENDING_PROJECT, CORRECTION_REQUIRED} and _employee_user(doc.employee) != frappe.session.user,
		"can_return_entries": active_employee and open_project_review and doc.docstatus == 0 and doc.custom_weekly_status in {WEEKLY_DRAFT, PENDING_PROJECT, CORRECTION_REQUIRED, PENDING_HR} and _employee_user(doc.employee) != frappe.session.user,
		"logs": logs,
	}


@frappe.whitelist()
def get_timesheet_review_detail(name: str):
	_require_hr()
	doc = frappe.get_doc("Timesheet", name)
	data = _serialize_weekly(doc)
	data["review_blockers"] = _hr_review_blockers(doc)
	data["source_timezone"] = frappe.utils.get_system_timezone()
	for row in data["time_logs"]:
		row["project_label"] = _project_display_name(row["project"])
	return data


@frappe.whitelist(methods=["POST"])
def return_timesheet_entries(name: str, entries, reason: str, stage: str = "project"):
	"""Return saved time intervals, without unlocking their unselected siblings."""
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A return reason is required."))
	entries = frappe.parse_json(entries) if isinstance(entries, str) else entries
	if not isinstance(entries, list) or not entries or any(not isinstance(item, str) for item in entries):
		frappe.throw(_("Select at least one time entry."))
	doc = frappe.get_doc("Timesheet", name)
	if not cint(doc.custom_is_weekly) or doc.docstatus != 0:
		frappe.throw(_("Only open weekly timesheets can be returned."))
	selected = [row for row in doc.time_logs if row.name in set(entries)]
	if {row.name for row in selected} != set(entries):
		frappe.throw(_("A selected entry does not belong to this timesheet."))
	draft = doc.custom_weekly_status == WEEKLY_DRAFT
	if stage == "hr":
		_require_hr()
		if not draft and doc.custom_weekly_status not in {PENDING_HR, CORRECTION_REQUIRED}:
			frappe.throw(_("This weekly timesheet is not ready for HR review."))
	elif stage == "project":
		for project in {row.project for row in selected}:
			if not _is_hr() and frappe.session.user != _project_lead_user(project) and frappe.session.user != _project_manager_user(project):
				frappe.throw(_("You cannot review entries for this project."), frappe.PermissionError)
			approval = next((row for row in doc.custom_project_approvals if row.project == project), None)
			if not draft and (not approval or approval.status not in {APPROVAL_PENDING, APPROVAL_RETURNED} or doc.custom_weekly_status not in {PENDING_PROJECT, CORRECTION_REQUIRED}):
				frappe.throw(_("This project review is no longer open."))
	else:
		frappe.throw(_("Invalid review stage."))

	if draft:
		# Drafts remain editable and unsubmitted; feedback applies only to these rows.
		for row in selected:
			row.custom_return_reason = reason
	else:
		_mark_correction(doc, selected, reason)
		for approval in doc.custom_project_approvals:
			if approval.project in {row.project for row in selected}:
				approval.status = APPROVAL_RETURNED
				approval.return_reason = reason
				approval.reviewed_by = frappe.session.user
				approval.reviewed_at = now_datetime()
	for approval in doc.custom_project_approvals:
		reviews = _entry_reviews(doc, approval)
		for log in selected:
			reviews.pop(log.name, None)
		approval.entry_reviews = json.dumps(reviews)
	doc.flags.weekly_action = "entry_return"
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", _("Time entries {0} returned for correction: {1}").format(
		", ".join(sorted(set(entries))), reason
	))
	_notify([_employee_user(doc.employee)], _("Time entries need correction"), reason, doc.name)
	return {"status": doc.custom_weekly_status, "returned": len(selected)}


@frappe.whitelist(methods=["POST"])
def reopen_weekly_timesheet(name: str, expected_modified: str, reason: str):
	"""Withdraw an open submission; preserve time and unchanged revision approvals."""
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("A reason for reopening the week is required."))
	frappe.db.sql("SELECT name FROM `tabTimesheet` WHERE name=%s FOR UPDATE", name)
	doc = frappe.get_doc("Timesheet", name)
	if not _is_hr():
		_assert_employee_owns(doc)
	if not cint(doc.custom_is_weekly) or doc.docstatus != 0 or doc.custom_weekly_status not in {PENDING_PROJECT, PENDING_HR, CORRECTION_REQUIRED} or not doc.custom_weekly_submitted_at:
		frappe.throw(_("Only a submitted week awaiting review can be reopened. Finalized weeks remain locked."))
	if not expected_modified or str(doc.modified) != str(expected_modified):
		frappe.throw(_("This week changed. Refresh before reopening it."))
	previous_status = doc.custom_weekly_status
	doc.custom_weekly_status = WEEKLY_DRAFT
	doc.custom_weekly_submitted_at = None
	doc.custom_correction_scope = None
	doc.custom_weekly_return_reason = None
	doc.flags.weekly_action = "week_reopen"
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", _("Submission withdrawn from {0} by {1}. All saved time retained. Reason: {2}").format(previous_status, frappe.session.user, reason))
	_notify([_employee_user(doc.employee)] + _hr_users(), _("Weekly timesheet reopened for editing"), reason, doc.name)
	return _serialize_weekly(doc)


@frappe.whitelist()
def hr_return_weekly_timesheet(name: str, reason: str):
	_require_hr()
	if not (reason or "").strip():
		frappe.throw(_("A return reason is required."))

	doc = frappe.get_doc("Timesheet", name)
	if not cint(doc.custom_is_weekly) or doc.custom_weekly_status != PENDING_HR:
		frappe.throw(_("This weekly timesheet is not ready for HR review."))

	for row in doc.custom_project_approvals:
		row.entry_reviews = "{}"
		row.status = APPROVAL_RETURNED
		row.return_reason = reason.strip()
		row.reviewed_by = frappe.session.user
		row.reviewed_at = now_datetime()
	_mark_correction(doc, doc.time_logs, reason.strip(), [row.project for row in doc.time_logs])
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
	frappe.db.sql("SELECT name FROM `tabTimesheet` WHERE name=%s FOR UPDATE", name)
	doc = frappe.get_doc("Timesheet", name)
	_refresh_review_routing(doc)
	if not cint(doc.custom_is_weekly) or doc.docstatus != 0 or not doc.custom_weekly_submitted_at or doc.custom_weekly_status != PENDING_HR:
		frappe.throw(_("This weekly timesheet is not ready for HR review."))

	if not _project_reviews_ready(doc):
		frappe.throw(_("All project sections must complete Project Lead review before HR can close the week."))

	for row in doc.custom_project_approvals:
		if row.status == APPROVAL_HR:
			row.entry_reviews = json.dumps({log.name: {"revision": _entry_revision(log), "reviewed_by": frappe.session.user, "reviewed_at": str(now_datetime())} for log in doc.time_logs if log.project == row.project})
			row.status = APPROVAL_APPROVED
			row.reviewed_by = frappe.session.user
			row.reviewed_at = now_datetime()
	doc.custom_weekly_status = CLOSED
	doc.custom_weekly_closed_at = now_datetime()
	doc.custom_weekly_return_reason = None
	doc.custom_correction_scope = None
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


def _project_display_name(project):
	label = frappe.db.get_value("Project", project, "project_name") if project else None
	return f"{label} · {project}" if label and label != project else project or ""


def _hr_employee_image(employee):
	from hrms.api.profile_photo import directory_image
	return directory_image(employee, frappe.db.get_value("Employee", employee, "image"))


def _hr_review_blockers(doc):
	if doc.custom_weekly_status == CLOSED:
		return []
	items = []
	if doc.custom_weekly_status == CORRECTION_REQUIRED:
		items.append(_("Employee must correct and resubmit this week."))
	for row in doc.custom_project_approvals:
		if row.status in {APPROVAL_PENDING, APPROVAL_RETURNED}:
			user = frappe.db.get_value("User", row.controller, "full_name") if row.controller else None
			items.append(_("{0}: {1} · {2}").format(_project_display_name(row.project), _(row.status), user or _("Unassigned reviewer")))
	if not _project_reviews_ready(doc) and not items:
		items.append(_("Project review is incomplete. Check the assigned reviewer and project review records."))
	return items


@frappe.whitelist()
def get_hr_weekly_timesheet_queue(view: str = "ready") -> list[dict]:
	"""HR oversight of submitted weeks; finalization remains independently guarded."""
	_require_hr()
	if view not in {"current", "history", "ready"}:
		frappe.throw(_("Unknown timesheet view."))

	weeks = frappe.get_list(
		"Timesheet",
		filters={
			"custom_is_weekly": 1,
			"custom_weekly_status": CLOSED if view == "history" else ("in", [PENDING_PROJECT, CORRECTION_REQUIRED, PENDING_HR]),
			"custom_weekly_submitted_at": ("is", "set"),
			"docstatus": 1 if view == "history" else 0,
		},
		fields=[
			"name",
			"employee",
			"employee_name",
			"custom_week_start",
			"custom_week_end",
			"total_hours",
			"modified",
		],
		order_by="custom_week_start desc, employee_name asc",
		limit_page_length=500,
	)

	result = []
	for week in weeks:
		doc = frappe.get_doc("Timesheet", week.name)
		_refresh_review_routing(doc)
		ready = doc.docstatus == 0 and doc.custom_weekly_status == PENDING_HR and _project_reviews_ready(doc)
		if view == "ready" and doc.custom_weekly_status != PENDING_HR:
			continue
		projects = {}
		for log in doc.time_logs:
			if not log.from_time:
				continue
			day = str(get_datetime(log.from_time).date())
			project_name = log.project or _("No Project")
			project = projects.setdefault(
				project_name, {"project": project_name, "daily_hours": {}}
			)
			project["daily_hours"][day] = project["daily_hours"].get(day, 0) + flt(log.hours)

		result.append(
			{
				"name": week.name,
				"employee": week.employee,
				"employee_name": week.employee_name,
				"week_start": str(week.custom_week_start),
				"week_end": str(week.custom_week_end),
				"total_hours": round(flt(week.total_hours), 2),
				"modified": str(week.modified),
				"ready_for_hr_close": ready,
				"week_status": doc.custom_weekly_status,
				"employee_image": _hr_employee_image(doc.employee),
				"review_blockers": _hr_review_blockers(doc),
				"project_labels": [_project_display_name(project) for project in projects],
				"activity_types": sorted({log.activity_type for log in doc.time_logs if log.activity_type}),
				"projects": [
					{
						"project": project["project"],
						"daily_hours": project["daily_hours"],
						"total_hours": round(sum(project["daily_hours"].values()), 2),
					}
					for project in projects.values()
				],
				"time_logs": [_serialize_row(row) for row in doc.time_logs],
			}
		)
	return result


def _weekly_overlap_seconds(doc, row):
	from hrms.utils.time_overlap import overlap_seconds
	if not row.from_time or not row.to_time:
		return 0
	start, end = get_datetime(row.from_time), get_datetime(row.to_time)
	intervals = [(get_datetime(other.from_time), get_datetime(other.to_time)) for other in doc.time_logs
		if other.idx != row.idx and other.from_time and other.to_time]
	# Retain the framework's employee/user scope, including other active documents.
	external = frappe.db.sql("""SELECT detail.from_time, detail.to_time
		FROM `tabTimesheet Detail` detail INNER JOIN `tabTimesheet` ts ON ts.name = detail.parent
		WHERE ts.name != %s AND ts.docstatus < 2
		AND ((%s != '' AND ts.employee = %s) OR (%s != '' AND ts.user = %s))
		AND detail.from_time < %s AND detail.to_time > %s""",
		(doc.name or "", doc.employee or "", doc.employee or "", doc.user or "", doc.user or "", end, start))
	intervals.extend((get_datetime(left), get_datetime(right)) for left, right in external)
	return overlap_seconds(start, end, intervals)


def validate_weekly_overlap(doc, row):
	from hrms.utils.time_overlap import MAX_OVERLAP_SECONDS
	seconds = _weekly_overlap_seconds(doc, row)
	if seconds > MAX_OVERLAP_SECONDS:
		frappe.throw(_("Row {0}: Time overlaps existing entries by {1} minutes. The maximum is 5 minutes.").format(
			row.idx, flt(seconds / 60, 2)))


def weekly_overlap_warnings(doc):
	from hrms.utils.time_overlap import MAX_OVERLAP_SECONDS
	return [dict(row=row.idx, minutes=flt(seconds / 60, 2)) for row in doc.time_logs
		if 0 < (seconds := _weekly_overlap_seconds(doc, row)) <= MAX_OVERLAP_SECONDS]


def _validate_time_rows(doc):
	if not doc.time_logs:
		return
	week_start = getdate(doc.custom_week_start)
	week_end = getdate(doc.custom_week_end)
	week_start_dt = datetime.combine(week_start, time.min)
	week_end_exclusive = datetime.combine(add_days(week_end, 1), time.min)

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
		validate_weekly_overlap(doc, row)


def prepare_weekly_document(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)):
		return
	for row in doc.time_logs:
		row.activity_type = row.activity_type or "Unassigned"


def notify_saved_team_entries(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)) or doc.docstatus != 0:
		return
	old = doc.get_doc_before_save()
	if old and doc.flags.get("weekly_action") in {None, "employee_save"}:
		current = {row.name: row for row in doc.time_logs}
		invalidated = []
		for approval in old.custom_project_approvals:
			for row in old.time_logs:
				if row.project != approval.project or row.name not in _entry_reviews(old, approval):
					continue
				if row.name not in current or _entry_revision(current[row.name]) != _entry_revision(row):
					invalidated.append({"entry": _row_payload(row), "review": _entry_reviews(old, approval)[row.name]})
		if invalidated:
			doc.add_comment("Comment", _("Previously reviewed entries changed or removed; their approvals no longer apply: {0}").format(
				frappe.utils.escape_html(json.dumps(invalidated, default=str))))
	previous = {row.project for row in old.time_logs} if old else set()
	for project in sorted({row.project for row in doc.time_logs if row.project} - previous):
		lead = _project_lead_user(project)
		if not lead or lead == _employee_user(doc.employee):
			continue
		label = frappe.db.get_value("Project", project, "project_name") or project
		_notify([lead], _("New team time entry saved"),
			_("{0} recorded time on {1}. The saved entries are available for review.").format(doc.employee_name, label), doc.name)


def validate_weekly_document(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)):
		return
	if not doc.custom_weekly_status:
		doc.custom_weekly_status = WEEKLY_DRAFT
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
		if old and not action and (
			old.get("custom_correction_scope") != doc.get("custom_correction_scope")
			or old.get("custom_weekly_return_reason") != doc.get("custom_weekly_return_reason")
			or [(row.name, row.project, row.controller, row.status, row.return_reason, row.get("entry_reviews")) for row in old.custom_project_approvals]
			!= [(row.name, row.project, row.controller, row.status, row.return_reason, row.get("entry_reviews")) for row in doc.custom_project_approvals]
		):
			frappe.throw(_("Review fields can only be changed through workflow actions."))
		if old and not action:
			old_reasons = {row.name: row.get("custom_return_reason") for row in old.time_logs}
			if any(row.get("custom_return_reason") != old_reasons.get(row.name) for row in doc.time_logs):
				frappe.throw(_("Correction reasons can only be changed through workflow actions."))
		if old and old.custom_weekly_status == CORRECTION_REQUIRED and not action:
			if old.employee != doc.employee or old.custom_week_start != doc.custom_week_start:
				frappe.throw(_("The employee and week cannot be changed during correction."))
			_validate_correction_changes(old, [_row_payload(row) for row in doc.time_logs])

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
	old = doc.get_doc_before_save() if not doc.is_new() else None
	action = doc.flags.get("weekly_action")
	if old and action not in {"project_lead_review", "entry_return", "hr_return", "hr_close", "employee_submit"}:
		old_logs = {row.name: row for row in old.time_logs}
		for row in doc.time_logs:
			previous = old_logs.get(row.name)
			if previous and _entry_revision(previous) != _entry_revision(row):
				row.custom_return_reason = None
		# Never accept review metadata supplied by an employee, including via
		# generic document writes. Rebuild only from the saved BEFORE image.
		doc.set("custom_project_approvals", [row.as_dict() for row in old.custom_project_approvals])
	if doc.docstatus == 0 and action != "hr_close":
		_set_project_approvals(doc)


def before_weekly_submit(doc):
	if not cint(getattr(doc, "custom_is_weekly", 0)):
		return
	if doc.flags.get("weekly_action") != "hr_close" or not _is_hr():
		frappe.throw(_("Only HR can close a fully approved weekly timesheet."), frappe.PermissionError)
	if not doc.custom_weekly_submitted_at:
		frappe.throw(_("The employee must submit the complete week before final HR approval."))
	if doc.custom_weekly_status != CLOSED:
		frappe.throw(_("Weekly timesheet must be in Closed status before final submission."))
	if not _project_reviews_ready(doc):
		frappe.throw(_("All project sections must be approved before final submission."))


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
				editable = _correction_scope(doc)["projects"]
				if project not in editable:
					frappe.throw(_("New timer entries are not allowed during a single-entry correction."))
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
