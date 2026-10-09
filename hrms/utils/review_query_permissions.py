"""Native Frappe read conditions for HR oversight's custom SQL reports.

Project-lead review is an existing explicit delegation outside native master/own
list access. Its separate server-enforced project scope remains unchanged here.
"""
import re

import frappe
from frappe import _


DOCTYPES = {"Timesheet", "Project"}


def hr_read_condition(doctype, alias=None):
	from hrms.api.weekly_timesheet import _is_hr
	if doctype not in DOCTYPES or alias and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", alias):
		frappe.throw(_("Unsupported review permission scope."), frappe.PermissionError)
	if not _is_hr():
		return ""
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("No permission to read {0}.").format(_(doctype)), frappe.PermissionError)
	from frappe.desk.reportview import get_match_cond
	condition = re.sub(r"^\s*and\s+", "", get_match_cond(doctype), count=1, flags=re.IGNORECASE).strip()
	if alias:
		condition = condition.replace(f"`tab{doctype}`", f"`{alias}`")
	return condition


def apply_hr_read_condition(query, doctype, allow_unassigned=None):
	condition = hr_read_condition(doctype)
	if not condition:
		return query
	from pypika.terms import Criterion
	class ReadPermissionCriterion(Criterion):
		def get_sql(self, **kwargs):
			return condition
	criterion = ReadPermissionCriterion()
	if allow_unassigned is not None:
		criterion = criterion | allow_unassigned.isnull() | (allow_unassigned == "")
	return query.where(criterion)


def check_hr_review_permission(doc, permission="read", project=None):
	"""Guard known-document HR endpoints without changing lead delegation."""
	from hrms.api.weekly_timesheet import _is_hr
	if not _is_hr():
		return
	doc.check_permission(permission)
	projects = {project} if project else {row.project for row in doc.time_logs if row.project}
	for name in projects:
		frappe.get_doc("Project", name).check_permission("read")
