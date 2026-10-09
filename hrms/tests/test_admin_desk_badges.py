"""Review counters under real Frappe row permissions on synthetic QA records."""
import unittest

import frappe

from hrms.api import admin_desk
from hrms.tests import test_team_queue_order as fixtures


class TestAdminDeskBadges(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fixtures.TestTeamQueueOrder.setUpClass.__func__(cls)

	setUp = fixtures.TestTeamQueueOrder.setUp
	tearDown = fixtures.TestTeamQueueOrder.tearDown

	def seed(self):
		fixtures.TestTeamQueueOrder.seed(self)
		frappe.set_user("Administrator")
		frappe.db.delete("User Permission", {"user": self.users[2], "allow": ("in", ["Employee", "Company"])})
		frappe.clear_cache(user=self.users[2])
		for doctype, state_field, statuses in (
			("Leave Application", "status", ["Open"] * 64 + ["Approved", "Rejected"]),
			("Expense Claim", "approval_status", ["Draft"] * 3 + ["Approved", "Rejected"]),
			("Employee Holiday", "status", ["Submitted"] * 65 + ["Approved", "Draft"]),
			("Employee Schedule", "status", ["Submitted"] * 4 + ["Approved", "Draft"]),
			("Employee Invoice", "status", ["Pending HR Review"] * 5 + ["Draft", "Changes Requested", "Pending Employee Confirmation", "Approved for Payment", "Paid", "Cancelled"]),
		):
			frappe.db.delete(doctype, {"name": ("like", "QA-BADGE-%"), "employee": self.employees[0]})
			for index, status in enumerate(statuses):
				values = dict(doctype=doctype, name=f"QA-BADGE-{doctype.replace(' ', '-')}-{index}",
					employee=self.employees[0], employee_name="Synthetic worker", company="_Test Company",
					employee_user=self.users[0], year=2026, status=status,
					leave_approver=self.users[2], expense_approver=self.users[2], docstatus=0)
				values[state_field] = status
				frappe.get_doc(values).db_insert()
		frappe.set_user(self.users[2])

	def test_full_counts_exclude_final_drafts_and_blocked_hr_weeks(self):
		self.seed()
		self.assertEqual(admin_desk.get_admin_desk_counts(), {
			"hr-timesheets": 12, "Leave Application": 64, "Expense Claim": 3,
			"Employee Holiday": 65, "Employee Schedule": 4, "Employee Invoice": 5,
		})
		frappe.set_user("Administrator")
		frappe.db.set_value("Employee Holiday", "QA-BADGE-Employee-Holiday-0", "status", "Approved")
		frappe.set_user(self.users[2])
		self.assertEqual(admin_desk.get_admin_desk_counts()["Employee Holiday"], 64)

	def test_count_respects_inherited_employee_permissions(self):
		self.seed()
		frappe.set_user("Administrator")
		frappe.get_doc(dict(doctype="User Permission", user=self.users[2], allow="Employee", for_value=self.employees[2])).insert()
		frappe.clear_cache(user=self.users[2])
		frappe.set_user(self.users[2])
		self.assertTrue(all(value == 0 for value in admin_desk.get_admin_desk_counts().values()))

	def test_no_counter_leak_for_hidden_cards_and_supported_icons(self):
		self.seed()
		for user in self.users:
			frappe.set_user(user)
			items = [item for section in admin_desk.get_admin_desk_sections() for item in section["items"]]
			self.assertTrue(all(item["icon"] in admin_desk.CARD_ICONS.values() for item in items))
			self.assertEqual(set(admin_desk.get_admin_desk_counts()), {item["count_key"] for item in items if "count_key" in item})

	def test_assigned_approver_does_not_count_their_own_unassigned_request(self):
		self.seed()
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", self.users[1])
		user.add_roles("Leave Approver")
		frappe.db.set_value("Employee", self.employees[0], "leave_approver", self.users[1])
		name = "QA-BADGE-Leave-Application-0"
		frappe.db.set_value("Leave Application", name, "leave_approver", self.users[1])
		frappe.share.add("Leave Application", name, self.users[1], read=1, write=1)
		frappe.get_doc(dict(doctype="Leave Application", name="QA-BADGE-OWN-LEAVE", employee=self.employees[1],
			employee_name="Synthetic lead", status="Open", docstatus=0, leave_approver=self.users[2])).db_insert()
		frappe.clear_cache(user=self.users[1])
		frappe.set_user(self.users[1])
		self.assertEqual(admin_desk.get_admin_desk_counts()["Leave Application"], 1)
