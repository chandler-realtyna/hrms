"""Explicit HR reminders for an observed, submitted project review section."""
from html import escape

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime
from hrms.utils.review_query_permissions import check_hr_review_permission
from hrms.api.weekly_timesheet import (
	_require_hr, _employee_user, _employee_has_active_account, _project_lead_user,
	_project_lead_employee, PENDING_PROJECT, APPROVAL_PENDING,
)


def _reminder_subject(project):
	return "Project review reminder: " + escape(project)


def _reminder_recipient(project, owner_user):
	def eligible(user):
		return bool(user and user != owner_user and frappe.db.get_value("User", user, "enabled")
			and frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name"))
	lead_user = _project_lead_user(project)
	if eligible(lead_user):
		return lead_user
	# Legacy manager helper raises for unusable assignments; a notification
	# fallback must simply return None, never break the entire review queue.
	manager = frappe.db.get_value("Project", project, "custom_project_manager")
	manager_user = frappe.db.get_value("Employee", {"name": manager, "status": "Active"}, "user_id") if manager else None
	return manager_user if eligible(manager_user) else None


@frappe.whitelist(methods=["POST"])
def ping_project_reviewer(name: str, project: str, expected_modified: str, expected_reviewer: str):
	_require_hr()
	frappe.db.sql("SELECT name FROM `tabTimesheet` WHERE name=%s FOR UPDATE", name)
	doc = frappe.get_doc("Timesheet", name)
	check_hr_review_permission(doc, "read", project)
	if not expected_modified or str(doc.modified) != str(expected_modified):
		frappe.throw(_("This week changed. Refresh before sending a reminder."))
	owner = _employee_user(doc.employee)
	if owner == frappe.session.user:
		frappe.throw(_("Your own week requires another HR reviewer."), frappe.PermissionError)
	if doc.docstatus != 0 or not doc.custom_is_weekly or doc.custom_weekly_status != PENDING_PROJECT or not doc.custom_weekly_submitted_at:
		frappe.throw(_("Reminders are available only for submitted weeks awaiting project review."))
	if not _employee_has_active_account(doc.employee):
		frappe.throw(_("This employee is inactive. The section is archived for HR follow-up."))
	approval = next((row for row in doc.custom_project_approvals if row.project == project), None)
	if not approval or approval.status != APPROVAL_PENDING or not any(row.project == project for row in doc.time_logs):
		frappe.throw(_("This project section is no longer awaiting project review."))
	if _project_lead_employee(project) == doc.employee:
		frappe.throw(_("Own-project entries require HR review, not a reminder to the project lead."))
	recipient = _reminder_recipient(project, owner)
	if not recipient or recipient == frappe.session.user:
		frappe.throw(_("No other active project reviewer is available. Review the assignment."))
	if not expected_reviewer or recipient != expected_reviewer:
		frappe.throw(_("The project reviewer changed. Refresh before sending the reminder."))
	subject = _reminder_subject(project)
	last = frappe.db.get_value("Notification Log", {"document_type": "Timesheet", "document_name": name, "for_user": recipient, "subject": subject}, "creation", order_by="creation desc")
	if last and get_datetime(last) > add_to_date(now_datetime(), hours=-24):
		return {"sent": False, "last_ping_at": str(last), "reviewer_name": frappe.db.get_value("User", recipient, "full_name") or recipient, "message": _("A reminder was already sent to this reviewer in the last 24 hours.")}
	project_label = frappe.db.get_value("Project", project, "project_name") or project
	message = escape(_("HR requests review of {0}'s submitted week {1} to {2}, project {3}.").format(doc.employee_name, doc.custom_week_start, doc.custom_week_end, project_label))
	frappe.get_doc({"doctype": "Notification Log", "subject": subject, "email_content": message, "for_user": recipient, "type": "Alert", "document_type": "Timesheet", "document_name": name}).insert(ignore_permissions=True)
	# Every explicit reminder must reach the employee's HRMS bell; do not suppress
	# it just because an older notification exists for the same weekly document.
	frappe.get_doc({"doctype": "PWA Notification", "from_user": frappe.session.user, "to_user": recipient, "message": subject + ": " + message, "reference_document_type": "Timesheet Project Approval", "reference_document_name": f"{project}|{doc.custom_week_start}"}).insert(ignore_permissions=True)
	doc.add_comment("Comment", _("HR sent a project review reminder to {0} for project {1}.").format(frappe.bold(escape(recipient)), frappe.bold(escape(project))))
	return {"sent": True, "last_ping_at": str(now_datetime()), "reviewer_name": frappe.db.get_value("User", recipient, "full_name") or recipient, "message": _("Reminder sent to the current project reviewer.")}
