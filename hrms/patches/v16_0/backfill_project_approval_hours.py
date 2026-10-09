"""Backfill Total Hours on Timesheet Project Approval rows.

The Total Hours column was added after approval rows already existed, so older
rows show blank until their timesheet is next saved (every save refreshes them
via validate). This patch fills them all in once from the parent time logs.

Idempotent: re-running only rewrites the same sums.
"""

import frappe
from frappe.utils import flt


def execute():
	approvals = frappe.get_all(
		"Timesheet Project Approval",
		fields=["name", "parent", "project"],
		limit_page_length=0,
	)
	parents = {}
	for approval in approvals:
		if approval.parent not in parents:
			try:
				parents[approval.parent] = frappe.get_doc("Timesheet", approval.parent)
			except frappe.DoesNotExistError:
				parents[approval.parent] = None
		doc = parents[approval.parent]
		if doc is None:
			continue
		total = round(
			sum(flt(row.hours) for row in doc.time_logs if row.project == approval.project),
			2,
		)
		frappe.db.set_value("Timesheet Project Approval", approval.name, "total_hours", total)
