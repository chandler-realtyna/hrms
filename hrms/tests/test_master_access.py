"""Actual framework access regressions, restricted to synthetic qa.local."""
import unittest

import frappe
from frappe.client import get
from frappe.permissions import add_permission, update_permission_property

from hrms.tests import test_shared_work_state as fixtures
from hrms.api.admin_desk import get_admin_desk_sections
from hrms.utils import master_access as access


class TestMasterAccess(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fixtures.TestSharedWorkState.setUpClass.__func__(cls)
		from hrms.patches.v16_0.setup_company_director_scope import execute
		execute()
		frappe.db.commit()

	def setUp(self):
		fixtures.TestSharedWorkState.setUp(self)
		frappe.clear_cache()

	def tearDown(self):
		fixtures.TestSharedWorkState.tearDown(self)
		frappe.clear_cache()

	def test_worker_and_lead_have_no_management_cards(self):
		for user in self.users[:2]:
			frappe.set_user(user)
			cards = [i for section in get_admin_desk_sections() for i in section["items"]]
			self.assertFalse({"User", "Employee", "Project"}.intersection(i.get("doctype") for i in cards))
			self.assertFalse(any(i.get("count_key") for i in cards))
			if user == self.users[1]:
				self.assertTrue(any(i["route"].endswith("project-timesheets") for i in cards))

	def test_user_directory_and_direct_api_deny_foreign_profiles(self):
		frappe.set_user(self.users[0])
		self.assertEqual(frappe.get_list("User", pluck="name", limit_page_length=0), [self.users[0]])
		self.assertEqual(get("User", self.users[0])["name"], self.users[0])
		for user in self.users[1:]:
			for ptype in ("read", "write", "delete", "share"):
				self.assertFalse(frappe.has_permission("User", ptype, doc=frappe.get_doc("User", user)))
			with self.assertRaises(frappe.PermissionError):
				get("User", user)

	def test_project_master_api_denied_but_all_timer_projects_remain_available(self):
		from hrms.api import timer_state
		from frappe.desk.search import search_link
		frappe.set_user(self.users[0])
		self.assertEqual(frappe.get_list("Project", pluck="name"), [])
		for project in self.projects:
			with self.assertRaises(frappe.PermissionError):
				get("Project", project)
			self.assertFalse(frappe.has_permission("Project", "write", doc=frappe.get_doc("Project", project)))
		rows = search_link("Project", "QA", page_length=20)
		self.assertTrue(set(self.projects).issubset(row["value"] for row in rows))
		state = timer_state.get_state()
		timer_state.apply_action("start", state["revision"], "master_access_start", {"project": self.projects[0]})
		self.assertEqual(timer_state.get_state()["timer"]["form"]["project"], self.projects[0])

	def test_profile_write_is_denied_even_with_self_service_role_grant(self):
		frappe.set_user("Administrator")
		add_permission("Employee", "Projects User")
		for ptype in ("read", "write"):
			update_permission_property("Employee", "Projects User", 0, ptype, 1)
		frappe.clear_cache()
		frappe.set_user(self.users[0])
		doc = frappe.get_doc("Employee", self.employees[0])
		self.assertTrue(frappe.has_permission("Employee", "read", doc=doc))
		self.assertFalse(frappe.has_permission("Employee", "write", doc=doc))
		doc.leave_approver = self.users[0]
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_other_booking_settings_and_meeting_details_are_private(self):
		frappe.set_user("Administrator")
		for dt in ("Employee Booking Settings", "Meeting Booking"):
			frappe.db.delete(dt, {"employee" if dt == "Employee Booking Settings" else "host_employee": ("in", self.employees)})
		for index in (0, 1):
			frappe.get_doc(dict(doctype="Employee Booking Settings", name=self.employees[index],
				employee=self.employees[index], booking_slug=f"qa-private-{index}")).db_insert()
			frappe.get_doc(dict(doctype="Meeting Booking", name=f"QA-PRIVATE-MEETING-{index}",
				host_employee=self.employees[index], booker_email="external@qa.invalid", title="Synthetic private meeting",
				start_datetime="2026-10-03 09:00:00", end_datetime="2026-10-03 10:00:00")).db_insert()
		frappe.set_user(self.users[0])
		self.assertEqual(frappe.get_list("Employee Booking Settings", pluck="name"), [self.employees[0]])
		self.assertEqual(frappe.get_list("Meeting Booking", pluck="name"), ["QA-PRIVATE-MEETING-0"])
		for dt, name in (("Employee Booking Settings", self.employees[1]), ("Meeting Booking", "QA-PRIVATE-MEETING-1")):
			with self.assertRaises(frappe.PermissionError):
				get(dt, name)

	def test_hr_and_directors_keep_master_permissions_and_lead_keeps_team_queue(self):
		frappe.set_user(self.users[0]); draft = fixtures.TestSharedWorkState.draft(self)
		frappe.set_user(self.users[1])
		from hrms.api.weekly_timesheet import get_team_timesheet_sections
		self.assertTrue(any(row["employee"] == self.employees[0] and row["project"] == self.projects[0]
			for row in get_team_timesheet_sections()["rows"]))
		frappe.set_user(self.users[2])
		self.assertTrue(access.can_manage_master("Project"))
		self.assertEqual(get("Project", self.projects[0])["name"], self.projects[0])
		self.assertEqual(get("Employee", self.employees[0])["name"], self.employees[0])
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", self.users[0])
		from hrms.patches.v16_0.create_company_director_access import _attach_director_profile
		_attach_director_profile(user)
		from hrms.utils.company_desk import sync_director_scope
		sync_director_scope(user)
		frappe.clear_cache(); frappe.set_user(self.users[0])
		for dt, name in (("User", self.users[1]), ("Employee", self.employees[1]), ("Project", self.projects[0])):
			with self.subTest(doctype=dt):
				self.assertEqual(get(dt, name)["name"], name)

	def test_activity_types_remain_read_only_for_contractors(self):
		frappe.set_user(self.users[0])
		doc = frappe.get_doc("Activity Type", "Unassigned")
		self.assertTrue(frappe.has_permission("Activity Type", "read", doc=doc))
		self.assertFalse(frappe.has_permission("Activity Type", "write", doc=doc))
