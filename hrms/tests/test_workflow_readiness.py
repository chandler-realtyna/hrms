import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

import frappe
from hrms.api import weekly_timesheet as workflow
from hrms.utils.expense_claimant import validate_claimant


def week(status="Approved", employee="EMP"):
	return frappe._dict(name="TEST-WEEK", employee=employee, custom_is_weekly=1, docstatus=0,
		custom_weekly_status=workflow.PENDING_HR, custom_week_start="2026-09-27",
		custom_weekly_submitted_at="2026-10-01 12:00:00", flags=frappe._dict(),
		time_logs=[frappe._dict(project="Alpha")],
		custom_project_approvals=[frappe._dict(project="Alpha", status=status)])


class TestReviewReadiness(unittest.TestCase):
	def test_first_saved_project_notifies_lead_before_submission(self):
		doc = week("Draft")
		doc.employee_name = "Employee"
		doc.get_doc_before_save = lambda: None
		with patch.object(workflow, "_project_lead_user", return_value="lead@example.test"), patch.object(workflow, "_employee_user", return_value="employee@example.test"), patch.object(frappe.db, "get_value", return_value="Project Alpha"), patch.object(workflow, "_notify") as notify:
			workflow.notify_saved_team_entries(doc)
		notify.assert_called_once()
		self.assertEqual(notify.call_args.args[0], ["lead@example.test"])

	def test_autosave_does_not_repeat_project_notice(self):
		doc = week("Draft")
		doc.get_doc_before_save = lambda: week("Draft")
		with patch.object(workflow, "_notify") as notify:
			workflow.notify_saved_team_entries(doc)
		notify.assert_not_called()

	def test_own_project_does_not_notify_employee_as_team_member(self):
		doc = week("Draft")
		doc.get_doc_before_save = lambda: None
		with patch.object(workflow, "_project_lead_user", return_value="lead@example.test"), patch.object(workflow, "_employee_user", return_value="lead@example.test"), patch.object(workflow, "_notify") as notify:
			workflow.notify_saved_team_entries(doc)
		notify.assert_not_called()

	def test_pending_returned_and_missing_reviews_are_not_ready(self):
		for status in ("Pending", "Returned", "Draft"):
			self.assertFalse(workflow._project_reviews_ready(week(status)))
		doc = week()
		doc.custom_project_approvals = []
		self.assertFalse(workflow._project_reviews_ready(doc))

	def test_duplicate_review_rows_are_not_ready(self):
		doc = week()
		doc.custom_project_approvals *= 2
		self.assertFalse(workflow._project_reviews_ready(doc))

	def test_all_projects_must_be_covered(self):
		doc = week()
		doc.time_logs.append(frappe._dict(project="Beta"))
		self.assertFalse(workflow._project_reviews_ready(doc))

	def test_approved_section_remains_ready(self):
		self.assertTrue(workflow._project_reviews_ready(week()))

	def test_hr_exception_cannot_skip_assigned_lead(self):
		with patch.object(workflow, "_project_lead_user", return_value="lead@example.test"), patch.object(workflow, "_project_lead_employee", return_value="LEAD"):
			self.assertFalse(workflow._project_reviews_ready(week("HR Review")))
			self.assertTrue(workflow._project_reviews_ready(week("HR Review", employee="LEAD")))

	def test_unavailable_lead_routes_to_hr(self):
		with patch.object(workflow, "_project_lead_user", return_value=None):
			self.assertTrue(workflow._project_reviews_ready(week("HR Review")))

	def test_hr_close_rejects_inconsistent_parent_before_mutation(self):
		doc = week("Pending")
		doc.save = Mock()
		with patch.object(workflow, "_require_hr"), patch.object(frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.ValidationError):
				workflow.hr_close_weekly_timesheet(doc.name)
		self.assertEqual(doc.custom_weekly_status, workflow.PENDING_HR)
		doc.save.assert_not_called()

	def test_native_final_submit_also_enforces_project_reviews(self):
		doc = week("Pending")
		doc.custom_weekly_status = workflow.CLOSED
		doc.flags.weekly_action = "hr_close"
		with patch.object(workflow, "_is_hr", return_value=True):
			with self.assertRaises(frappe.ValidationError):
				workflow.before_weekly_submit(doc)

	def test_lead_team_drafts_block_final_handoff_not_initial_submission(self):
		team = week("Pending", employee="OTHER")
		team.custom_weekly_submitted_at = None
		with patch.object(frappe, "get_all", side_effect=[["Alpha"], [frappe._dict(name="OTHER-WEEK", employee_name="Other employee")]]), patch.object(frappe, "get_doc", return_value=team):
			self.assertEqual(len(workflow._team_review_blockers(week())), 1)

	def test_personal_submission_is_staged_when_team_is_not_ready(self):
		doc = week("HR Review")
		doc.custom_weekly_status = workflow.WEEKLY_DRAFT
		doc.custom_weekly_submitted_at = None
		doc.save = Mock()
		doc.add_comment = Mock()
		with patch.object(frappe, "get_doc", return_value=doc), patch.object(workflow, "_assert_employee_owns"), patch.object(workflow, "_set_project_approvals"), patch.object(workflow, "_team_review_blockers", return_value=[{"employee_name": "Other lead"}]), patch.object(workflow, "_serialize_weekly", side_effect=lambda value: value.custom_weekly_status), patch.object(workflow, "_notify") as notify:
			self.assertEqual(workflow.submit_weekly_timesheet(doc.name), workflow.PENDING_PROJECT)
		self.assertIsNotNone(doc.custom_weekly_submitted_at)
		notify.assert_not_called()

	def test_approved_project_is_ready_even_if_other_project_needs_correction(self):
		team = week(employee="OTHER")
		team.custom_weekly_status = workflow.CORRECTION_REQUIRED
		team.custom_project_approvals.append(frappe._dict(project="Beta", status="Returned"))
		with patch.object(frappe, "get_all", side_effect=[["Alpha"], [frappe._dict(name="OTHER-WEEK", employee_name="Other employee")]]), patch.object(frappe, "get_doc", return_value=team):
			self.assertEqual(workflow._team_review_blockers(week()), [])

	def test_team_blocker_prevents_hr_close_before_mutation(self):
		doc = week()
		doc.save = Mock()
		with patch.object(workflow, "_require_hr"), patch.object(frappe, "get_doc", return_value=doc), patch.object(workflow, "_team_review_blockers", return_value=[{"employee_name": "Other"}]):
			with self.assertRaises(frappe.ValidationError):
				workflow.hr_close_weekly_timesheet(doc.name)
		doc.save.assert_not_called()

	def test_lead_week_advances_after_team_review_without_auto_approving(self):
		doc = week()
		doc.custom_weekly_status = workflow.PENDING_PROJECT
		doc.employee_name = "Lead"
		doc.save = Mock()
		doc.add_comment = Mock()
		with patch.object(frappe, "get_all", return_value=[doc.name]), patch.object(frappe, "get_doc", return_value=doc), patch.object(workflow, "_team_review_blockers", return_value=[]), patch.object(workflow, "_notify"), patch.object(workflow, "_hr_users", return_value=[]):
			workflow._refresh_ready_lead_weeks(doc.custom_week_start, "OTHER-WEEK", doc.employee)
		self.assertEqual(doc.custom_weekly_status, workflow.PENDING_HR)
		self.assertEqual(doc.docstatus, 0)
		doc.save.assert_called_once()


class TestExpenseClaimant(unittest.TestCase):
	def claim(self, employee="SELF", old=None):
		return SimpleNamespace(employee=employee, company="Company", is_new=lambda: old is None, get_doc_before_save=lambda: old)

	def test_employee_cannot_create_claim_for_someone_else(self):
		with patch.object(frappe, "session", SimpleNamespace(user="self@example.test")), patch.object(frappe, "get_roles", return_value=["Employee"]), patch.object(frappe.db, "get_value", return_value="other@example.test"):
			with self.assertRaises(frappe.PermissionError):
				validate_claimant(self.claim("OTHER"))

	def test_employee_can_create_own_claim(self):
		with patch.object(frappe, "session", SimpleNamespace(user="self@example.test")), patch.object(frappe, "get_roles", return_value=["Employee"]), patch.object(frappe.db, "get_value", side_effect=["self@example.test", "Company"]):
			validate_claimant(self.claim())

	def test_employee_cannot_choose_another_company_on_new_claim(self):
		with patch.object(frappe, "session", SimpleNamespace(user="self@example.test")), patch.object(frappe, "get_roles", return_value=["Employee"]), patch.object(frappe.db, "get_value", side_effect=["self@example.test", "Other Company"]):
			with self.assertRaises(frappe.PermissionError):
				validate_claimant(self.claim())

	def test_saved_claimant_cannot_be_changed_even_by_director(self):
		old = SimpleNamespace(employee="SELF", company="Company")
		with self.assertRaises(frappe.PermissionError):
			validate_claimant(self.claim("OTHER", old))

	def test_hr_can_create_on_behalf_without_changing_existing_claim(self):
		with patch.object(frappe, "session", SimpleNamespace(user="hr@example.test")), patch.object(frappe, "get_roles", return_value=["HR Manager"]):
			validate_claimant(self.claim("OTHER"))
