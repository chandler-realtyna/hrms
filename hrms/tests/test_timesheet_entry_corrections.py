import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from hrms.api import weekly_timesheet as workflow


class Record(dict):
	def __getattr__(self, name):
		return self.get(name)

	def __setattr__(self, name, value):
		self[name] = value


def entry(name, project="Alpha", hours=1):
	return Record(name=name, project=project, from_time="2026-09-27 09:00:00", to_time="2026-09-27 10:00:00", hours=hours, activity_type="Unassigned", description="Work", is_billable=0)


def document(status=workflow.PENDING_PROJECT):
	doc = Record(name="WEEK-TEST", employee="EMP-TEST", custom_is_weekly=1, docstatus=0, custom_weekly_status=status, custom_correction_scope=None)
	doc.time_logs = [entry("one"), entry("two")]
	doc.custom_project_approvals = [Record(name="approval", project="Alpha", controller="lead@example.test", status=workflow.APPROVAL_PENDING)]
	doc.flags = Record()
	doc.save = lambda **kwargs: None
	doc.add_comment = lambda *args: None
	return doc


class TestCorrectionScope(unittest.TestCase):
	def test_returned_entry_does_not_unlock_sibling(self):
		doc = document()
		workflow._mark_correction(doc, [doc.time_logs[0]], "Fix interval")
		self.assertEqual(workflow._correction_scope(doc), {"entries": ["one"], "projects": []})
		rows = copy.deepcopy(doc.time_logs)
		rows[0].description = "Corrected"
		workflow._validate_correction_changes(doc, rows)
		rows[1].hours = 2
		with self.assertRaises(frappe.ValidationError):
			workflow._validate_correction_changes(doc, rows)

	def test_deleting_returned_row_does_not_unlock_other_rows(self):
		doc = document()
		workflow._mark_correction(doc, [doc.time_logs[0]], "Remove duplicate")
		workflow._validate_correction_changes(doc, [doc.time_logs[1]])
		doc.time_logs.pop(0)
		changed = copy.deepcopy(doc.time_logs)
		changed[0].description = "Unauthorized change"
		with self.assertRaises(frappe.ValidationError):
			workflow._validate_correction_changes(doc, changed)

	def test_full_section_return_allows_new_entries_only_in_section(self):
		doc = document()
		workflow._mark_correction(doc, doc.time_logs, "Fix section", ["Alpha"])
		workflow._validate_correction_changes(doc, [entry(None)])
		with self.assertRaises(frappe.ValidationError):
			workflow._validate_correction_changes(doc, [entry(None, "Beta")])

	def test_unknown_or_duplicate_identifiers_are_rejected(self):
		doc = document()
		workflow._mark_correction(doc, doc.time_logs, "Fix section", ["Alpha"])
		for rows in ([entry("injected")], [entry("one"), entry("one")]):
			with self.assertRaises(frappe.ValidationError):
				workflow._validate_correction_changes(doc, rows)

	def test_legacy_return_remains_project_scoped(self):
		doc = document(workflow.CORRECTION_REQUIRED)
		doc.custom_project_approvals[0].status = workflow.APPROVAL_RETURNED
		self.assertEqual(workflow._correction_scope(doc)["projects"], ["Alpha"])

	def test_billable_change_on_locked_sibling_is_rejected(self):
		doc = document()
		workflow._mark_correction(doc, [doc.time_logs[0]], "Fix interval")
		rows = copy.deepcopy(doc.time_logs)
		rows[1].is_billable = 1
		with self.assertRaises(frappe.ValidationError):
			workflow._validate_correction_changes(doc, rows)

	def test_returned_entry_can_be_reassigned_without_unlocking_other_project(self):
		doc = document()
		doc.time_logs[1].project = "Beta"
		workflow._mark_correction(doc, [doc.time_logs[0]], "Wrong project")
		rows = copy.deepcopy(doc.time_logs)
		rows[0].project = "Beta"
		workflow._validate_correction_changes(doc, rows)
		rows[1].description = "Changed"
		with self.assertRaises(frappe.ValidationError):
			workflow._validate_correction_changes(doc, rows)

	def test_resubmission_requeues_returned_project_and_preserves_other_approval(self):
		doc = document(workflow.CORRECTION_REQUIRED)
		doc.time_logs[1].project = "Beta"
		doc.custom_project_approvals[0].status = workflow.APPROVAL_RETURNED
		doc.custom_project_approvals.append(Record(name="other", project="Beta", status=workflow.APPROVAL_APPROVED))
		with patch.object(workflow, "_project_lead_user", return_value="lead@example.test"), patch.object(workflow, "_project_lead_employee", return_value="LEAD-EMP"):
			workflow._set_project_approvals(doc)
		self.assertEqual(doc.custom_project_approvals[0].status, workflow.APPROVAL_PENDING)
		self.assertEqual(doc.custom_project_approvals[1].status, workflow.APPROVAL_APPROVED)

	def test_moving_returned_entry_requeues_previously_approved_destination(self):
		doc = document()
		doc.custom_project_approvals[0].status = workflow.APPROVAL_RETURNED
		doc.custom_project_approvals.append(Record(name="other", project="Beta", status=workflow.APPROVAL_APPROVED))
		workflow._mark_correction(doc, [doc.time_logs[0]], "Wrong project")
		doc.time_logs[0].project = "Beta"
		with patch.object(workflow, "_project_lead_user", return_value="lead@example.test"), patch.object(workflow, "_project_lead_employee", return_value="LEAD-EMP"):
			workflow._set_project_approvals(doc)
		self.assertEqual(doc.custom_project_approvals[1].status, workflow.APPROVAL_PENDING)


class TestEntryReturn(unittest.TestCase):
	def run_return(self, doc, entries, reason="Fix interval", roles=(), stage="project", manager_error=None):
		with patch.object(workflow.frappe, "get_doc", return_value=doc), patch.object(workflow.frappe, "get_roles", return_value=list(roles)), patch.object(workflow.frappe, "session", SimpleNamespace(user="lead@example.test")), patch.object(workflow, "_project_lead_user", return_value="lead@example.test"), patch.object(workflow, "_project_manager_user", return_value=None, side_effect=manager_error), patch.object(workflow, "_notify"), patch.object(workflow, "_employee_user", return_value="employee@example.test"):
			return workflow.return_timesheet_entries(doc.name, entries, reason, stage)

	def test_draft_can_be_returned_without_submitting_week(self):
		doc = document(workflow.WEEKLY_DRAFT)
		doc.custom_project_approvals = []
		self.run_return(doc, ["one"])
		self.assertEqual(doc.custom_weekly_status, workflow.WEEKLY_DRAFT)
		self.assertEqual(doc.time_logs[0].custom_return_reason, "Fix interval")
		self.assertIsNone(doc.time_logs[1].custom_return_reason)
		self.assertIsNone(doc.custom_correction_scope)

	def test_hr_return_affects_only_selected_record(self):
		doc = document(workflow.PENDING_HR)
		doc.custom_project_approvals[0].status = workflow.APPROVAL_APPROVED
		self.run_return(doc, ["two"], roles=["HR Manager"], stage="hr")
		self.assertEqual(json.loads(doc.custom_correction_scope)["entries"], ["two"])
		self.assertIsNone(doc.time_logs[0].custom_return_reason)

	def test_lead_return_does_not_depend_on_manager_account(self):
		doc = document(workflow.WEEKLY_DRAFT)
		self.run_return(doc, ["one"], manager_error=AssertionError("Manager lookup is not needed"))
		self.assertEqual(doc.time_logs[0].custom_return_reason, "Fix interval")

	def test_return_requires_reason_and_existing_record(self):
		for entries, reason in [(["one"], " "), (["foreign"], "Reason"), ([], "Reason")]:
			with self.assertRaises(frappe.ValidationError):
				self.run_return(document(), entries, reason)

	def test_closed_week_cannot_be_returned(self):
		doc = document(workflow.CLOSED)
		doc.docstatus = 1
		with self.assertRaises(frappe.ValidationError):
			self.run_return(doc, ["one"])

	def test_wrong_project_lead_cannot_return_draft(self):
		doc = document(workflow.WEEKLY_DRAFT)
		with patch.object(workflow, "_is_hr", return_value=False), patch.object(workflow, "_project_lead_user", return_value="other@example.test"), patch.object(workflow, "_project_manager_user", return_value=None), patch.object(workflow.frappe, "get_doc", return_value=doc), patch.object(workflow.frappe, "session", SimpleNamespace(user="intruder@example.test")):
			with self.assertRaises(frappe.PermissionError):
				workflow.return_timesheet_entries(doc.name, ["one"], "Reason")
