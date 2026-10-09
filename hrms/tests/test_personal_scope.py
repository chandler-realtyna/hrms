import unittest
from unittest.mock import patch

import frappe
from hrms.utils import personal_scope as scope


class TestPersonalScope(unittest.TestCase):
	def test_list_scope_is_employee_based_not_record_owner(self):
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe.db, "escape", return_value="'member@example.test'"):
			condition = scope.schedule_query("member@example.test")
		self.assertIn("`tabEmployee Schedule`.`employee`", condition)
		self.assertIn("user_id = 'member@example.test'", condition)
		self.assertNotIn("owner", condition)

	def test_employee_master_scope_uses_name(self):
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe.db, "escape", return_value="'member'"):
			self.assertIn("`tabEmployee`.`name` IN", scope.employee_query("member"))

	def test_designated_approvers_remain_in_request_scope(self):
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe.db, "escape", return_value="'approver'"):
			self.assertIn("`leave_approver` = 'approver'", scope.leave_query("approver"))
			self.assertIn("`expense_approver` = 'approver'", scope.expense_query("approver"))

	def test_manager_scope_does_not_override_standard_permissions(self):
		with patch.object(scope, "_is_manager", return_value=True):
			self.assertEqual(scope.timesheet_query("manager"), "")
			self.assertTrue(scope.has_personal_permission(frappe._dict(doctype="Timesheet"), user="manager"))

	def test_non_owner_cannot_open_or_write_other_employee_record(self):
		doc = frappe._dict(doctype="Employee Schedule", employee="OTHER")
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe.db, "get_value", return_value="other@example.test"):
			for ptype in ("read", "write", "delete", "submit", "export"):
				self.assertFalse(scope.has_personal_permission(doc, ptype, "member@example.test"))

	def test_owner_preserves_standard_role_permission_checks(self):
		doc = frappe._dict(doctype="Employee Holiday", employee="SELF")
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe.db, "get_value", return_value="member@example.test"):
			self.assertTrue(scope.has_personal_permission(doc, "read", "member@example.test"))

	def test_installed_frappe_controller_contract_accepts_authorized_user(self):
		from frappe.permissions import has_controller_permissions
		doc = frappe._dict(doctype="Timesheet", employee="SELF")
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe.db, "get_value", return_value="member@example.test"):
			self.assertTrue(has_controller_permissions(doc, "read", "member@example.test"))
			self.assertTrue(has_controller_permissions(doc, "write", "member@example.test"))
			self.assertFalse(has_controller_permissions(doc, "write", "other@example.test"))

	def test_designated_approver_keeps_existing_role_checks(self):
		doc = frappe._dict(doctype="Expense Claim", employee="OTHER", expense_approver="approver")
		with patch.object(scope, "_is_manager", return_value=False):
			self.assertTrue(scope.has_personal_permission(doc, "write", "approver"))

	def request(self, employee="SELF", status="Draft", old=None):
		doc = frappe._dict(employee=employee, status=status)
		doc.is_new = lambda: old is None
		doc.get_doc_before_save = lambda: old
		return doc

	def test_new_request_cannot_start_approved_or_rejected(self):
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe, "session", frappe._dict(user="member")), patch.object(frappe.db, "get_value", return_value="member"):
			for status in ("Approved", "Rejected"):
				with self.assertRaises(frappe.PermissionError):
					scope.validate_personal_request(self.request(status=status))

	def test_employee_can_create_own_draft_or_submission(self):
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe, "session", frappe._dict(user="member")), patch.object(frappe.db, "get_value", return_value="member"):
			for status in ("Draft", "Submitted"):
				scope.validate_personal_request(self.request(status=status))

	def test_employee_cannot_save_for_another_person(self):
		with patch.object(scope, "_is_manager", return_value=False), patch.object(frappe, "session", frappe._dict(user="member")), patch.object(frappe.db, "get_value", return_value="another"):
			with self.assertRaises(frappe.PermissionError):
				scope.validate_personal_request(self.request("OTHER"))

	def test_saved_request_cannot_be_reassigned_even_by_hr(self):
		with patch.object(scope, "_is_manager", return_value=True):
			with self.assertRaises(frappe.PermissionError):
				scope.validate_personal_request(self.request("OTHER", old=frappe._dict(employee="SELF")))

	def test_hr_can_review_existing_request(self):
		with patch.object(scope, "_is_manager", return_value=True):
			scope.validate_personal_request(self.request(status="Approved", old=frappe._dict(employee="SELF")))
