"""Real framework/database tests. Run only on a blank isolated QA site."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import frappe

from hrms.api import timer_state as timer
from hrms.api import weekly_timesheet as week
from hrms.utils.leave_routing import route_personal_leave


class TestSharedWorkState(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		if frappe.local.site != "qa.local":
			raise RuntimeError("These write tests require the isolated qa.local site.")
		frappe.set_user("Administrator")
		for leave_type in ("Paid Leave", "Sick Leave", "Unpaid Leave"):
			if not frappe.db.exists("Leave Type", leave_type):
				frappe.get_doc(dict(doctype="Leave Type", leave_type_name=leave_type,
					is_lwp=int(leave_type == "Unpaid Leave"))).insert()
		if not frappe.db.exists("Holiday List", "QA Calendar"):
			frappe.get_doc(dict(doctype="Holiday List", holiday_list_name="QA Calendar", from_date="2026-01-01", to_date="2026-12-31",
				holidays=[dict(holiday_date="2026-01-01", description="Synthetic holiday")])).insert()
		frappe.db.set_value("Company", "_Test Company", "default_holiday_list", "QA Calendar")
		if not frappe.db.exists("Activity Type", "Unassigned"):
			frappe.get_doc(dict(doctype="Activity Type", activity_type="Unassigned")).insert()
		cls.users = ["worker@qa.invalid", "lead@qa.invalid", "hr@qa.invalid"]
		cls.employees = []
		for user in cls.users:
			if not frappe.db.exists("User", user):
				frappe.get_doc(dict(doctype="User", email=user, first_name=user.split("@")[0],
					send_welcome_email=0, roles=[{"role": "Employee"}, {"role": "Projects User"}] +
					([{"role": "HR Manager"}] if user == cls.users[2] else []))).insert()
			name = frappe.db.get_value("Employee", {"user_id": user}, "name")
			if not name:
				name = frappe.get_doc(dict(doctype="Employee", first_name=user.split("@")[0],
					gender="Male", date_of_birth="1990-01-01", date_of_joining="2020-01-01",
					status="Active", company="_Test Company", user_id=user)).insert().name
			cls.employees.append(name)
		cls.projects = []
		for label in ("QA Alpha", "QA Beta"):
			name = frappe.db.get_value("Project", {"project_name": label}, "name")
			if not name:
				name = frappe.get_doc(dict(doctype="Project", project_name=label, status="Open", company="_Test Company", custom_project_lead=cls.employees[1])).insert().name
			frappe.db.set_value("Project", name, "custom_project_lead", cls.employees[1])
			cls.projects.append(name)
		frappe.db.set_single_value("HR Settings", "custom_employee_leave_approver", cls.users[2])
		frappe.db.commit()

	def setUp(self):
		frappe.set_user(self.users[0])
		frappe.db.savepoint("shared_state_test")
		for user in self.users:
			frappe.db.delete(timer.OPERATION, {"user": user})
			frappe.db.delete(timer.STATE, {"user": user})
		names = frappe.get_all("Timesheet", filters={"employee": ("in", self.employees)}, pluck="name")
		if names:
			for field in frappe.get_meta("Timesheet").get_table_fields():
				frappe.db.delete(field.options, {"parent": ("in", names), "parenttype": "Timesheet"})
			frappe.db.delete("Timesheet", {"name": ("in", names)})
		self.now = datetime(2026, 10, 2, 9, tzinfo=timezone.utc)
		self.clock = patch.object(timer, "_now", side_effect=lambda: self.now)
		self.clock.start()
		self.operation = 0

	def tearDown(self):
		self.clock.stop()
		frappe.db.rollback(save_point="shared_state_test")
		frappe.set_user("Administrator")

	def act(self, action, payload=None, revision=None, operation=None):
		self.operation += 1
		state = timer.get_state()
		return timer.apply_action(action, state["revision"] if revision is None else revision,
			operation or f"operation_{self.operation:08}", payload or {})

	def draft(self):
		data = week.get_weekly_timesheet(week_start="2026-09-27")
		data["time_logs"] = [dict(project=self.projects[0], activity_type="Unassigned", description="Synthetic work",
			from_time="2026-09-28 09:00:00", to_time="2026-09-28 10:00:00", hours=1)]
		return week.save_weekly_timesheet(data)

	def test_actual_framework_own_read_write_and_foreign_denial(self):
		doc = frappe.get_doc("Timesheet", self.draft()["name"])
		self.assertTrue(frappe.has_permission("Timesheet", "read", doc=doc))
		self.assertTrue(frappe.has_permission("Timesheet", "write", doc=doc))
		frappe.set_user(self.users[1])
		self.assertFalse(frappe.has_permission("Timesheet", "write", doc=doc))
		self.assertFalse(frappe.has_permission("Timesheet", "read", doc=doc))

	def test_week_stale_save_does_not_replace_rows(self):
		first = self.draft()
		stale = copy.deepcopy(first)
		first["note"] = "New version"
		week.save_weekly_timesheet(first, expected_modified=first["modified"])
		stale["note"] = "Stale overwrite"
		with self.assertRaises(frappe.TimestampMismatchError):
			week.save_weekly_timesheet(stale, expected_modified=stale["modified"])
		self.assertEqual(frappe.db.get_value("Timesheet", first["name"], "note"), "New version")

	def test_idempotent_replay_and_stale_device(self):
		first = self.act("start", {"project": self.projects[0]}, operation="same_operation")
		replayed = timer.apply_action("start", 0, "same_operation", {"project": self.projects[0]})
		self.assertEqual(first["revision"], replayed["revision"])
		with self.assertRaises(frappe.TimestampMismatchError):
			timer.apply_action("pause", 0, "other_operation", {})
		with self.assertRaises(frappe.ValidationError):
			timer.apply_action("pause", 0, "same_operation", {})

	def test_other_project_save_keeps_active_timer_and_replay_no_duplicate(self):
		self.act("start", {"project": self.projects[0]})
		self.now += timedelta(minutes=10)
		self.act("switch", {"project": self.projects[1]})
		self.now += timedelta(minutes=5)
		state = timer.get_state()
		saved = self.act("save", {"project": self.projects[0]}, operation="save_operation")
		self.assertEqual(saved["timer"]["form"]["project"], self.projects[1])
		self.assertEqual(saved["timer"]["startTime"], state["timer"]["startTime"])
		name = saved["saved_timesheets"][0]
		count = frappe.db.count("Timesheet Detail", {"parent": name})
		timer.apply_action("save", state["revision"], "save_operation", {"project": self.projects[0]})
		self.assertEqual(frappe.db.count("Timesheet Detail", {"parent": name}), count)

	def test_failed_save_preserves_all_pending_intervals(self):
		self.act("start", {"project": self.projects[0]})
		self.now += timedelta(minutes=5)
		self.act("pause")
		before = timer.get_state()
		with patch.object(week, "save_weekly_timer_log", side_effect=frappe.ValidationError("Rejected")):
			with self.assertRaises(frappe.ValidationError): self.act("save", {"project": self.projects[0]})
		self.assertEqual(timer.get_state()["timer"], before["timer"])

	def test_shared_favorites_and_account_isolation(self):
		self.act("favorite", {"project": self.projects[0]})
		self.assertEqual(timer.get_state()["favorites"], [self.projects[0]])
		frappe.set_user(self.users[1])
		self.assertEqual(timer.get_state()["favorites"], [])
		self.assertIsNone(timer.get_state()["timer"]["startTime"])

	def test_local_import_requires_owner_and_never_replaces_shared_state(self):
		legacy = timer._empty_timer()
		legacy.update(owner=self.users[1])
		with self.assertRaises(frappe.PermissionError): self.act("import", {"timer": legacy})
		legacy["owner"] = self.users[0]
		self.act("import", {"timer": legacy, "favorites": [self.projects[0], self.projects[0]]})
		self.assertEqual(timer.get_state()["favorites"], [self.projects[0]])
		with self.assertRaises(frappe.ValidationError): self.act("import", {"timer": legacy})

	def test_legacy_save_cannot_bypass_shared_timer(self):
		self.act("start", {"project": self.projects[0]})
		with self.assertRaises(frappe.ValidationError): timer.reject_legacy_save(self.users[0])

	def test_active_legacy_timer_without_project_is_not_imported(self):
		legacy = timer._empty_timer()
		legacy.update(owner=self.users[0], startTime=timer._iso(self.now))
		with self.assertRaises(frappe.ValidationError): self.act("import", {"timer": legacy})
		self.assertFalse(timer.get_state()["initialized"])

	def test_private_doctype_cannot_be_written_directly(self):
		doc = frappe.get_doc(timer.STATE, timer.get_state()["timer"]["owner"])
		doc.revision += 1
		with self.assertRaises(frappe.PermissionError): doc.save()

	def test_paused_autosave_uses_server_deadline(self):
		self.act("start", {"project": self.projects[0]})
		self.now += timedelta(minutes=5)
		self.act("pause")
		with self.assertRaises(frappe.ValidationError): self.act("autosave")
		self.now += timedelta(hours=2)
		result = self.act("autosave")
		self.assertFalse(result["timer"]["segments"])
		self.assertTrue(result["saved_timesheets"])

	def test_personal_leave_destination_fixed_but_submitted_unchanged(self):
		doc = frappe.get_doc(dict(doctype="Leave Application", employee=self.employees[0], leave_approver=self.users[1]))
		route_personal_leave(doc)
		self.assertEqual(doc.leave_approver, self.users[2])
		doc.name = "submitted-test"; doc.set("__islocal", 0); doc.docstatus = 1; doc.leave_approver = self.users[1]
		route_personal_leave(doc)
		self.assertEqual(doc.leave_approver, self.users[1])

	def test_team_queue_reads_draft_from_original_record_and_excludes_self(self):
		saved = self.draft()
		frappe.set_user(self.users[1])
		result = week.get_team_timesheet_sections()
		self.assertTrue(any(row.timesheet == saved["name"] for row in result["rows"]))
		self.assertTrue(all(row.employee != self.employees[1] for row in result["rows"]))
		self.assertTrue(all(not row.actionable for row in result["rows"]))

	def test_complete_correction_project_and_hr_workflow(self):
		data = self.draft()
		data["time_logs"].append(dict(project=self.projects[0], activity_type="Unassigned", description="Sibling",
			from_time="2026-09-28 10:00:00", to_time="2026-09-28 11:00:00", hours=1))
		data = week.save_weekly_timesheet(data)
		week.submit_weekly_timesheet(data["name"])
		frappe.set_user(self.users[1])
		week.return_timesheet_entries(data["name"], [data["time_logs"][0]["name"]], "Fix description", "project")
		frappe.set_user(self.users[0])
		returned = week.get_weekly_timesheet(data["name"])
		wrong = copy.deepcopy(returned)
		wrong["time_logs"][1]["description"] = "Locked sibling overwrite"
		with self.assertRaises(frappe.ValidationError): week.save_weekly_timesheet(wrong)
		returned["time_logs"][0]["description"] = "Corrected"
		week.save_weekly_timesheet(returned)
		week.submit_weekly_timesheet(data["name"])
		frappe.set_user(self.users[2])
		with self.assertRaises(frappe.ValidationError): week.hr_close_weekly_timesheet(data["name"])
		frappe.set_user(self.users[1])
		approval = frappe.db.get_value("Timesheet Project Approval", {"parent": data["name"], "project": self.projects[0]}, "name")
		week.approve_project_review(approval)
		frappe.set_user(self.users[2])
		final = week.hr_close_weekly_timesheet(data["name"])
		self.assertEqual(final["custom_weekly_status"], "Closed")
		frappe.set_user(self.users[0])
		with self.assertRaises(frappe.ValidationError): week.save_weekly_timesheet(final)
		frappe.set_user(self.users[1])
		self.assertFalse(any(row.timesheet == data["name"] for row in week.get_team_timesheet_sections()["rows"]))
		self.assertTrue(any(row.timesheet == data["name"] for row in week.get_team_timesheet_sections("history")["rows"]))

	def test_scoped_pagination_beyond_old_500_cap(self):
		from frappe.utils import add_days, get_datetime
		frappe.set_user("Administrator")
		for index in range(505):
			start = add_days("2026-09-27", -7*index)
			name = f"QA-PAGING-{index:04}"
			frappe.get_doc(dict(doctype="Timesheet", name=name, employee=self.employees[0],
				employee_name="Paging worker", company="_Test Company", custom_is_weekly=1,
				custom_week_key=f"{self.employees[0]}|{start}", custom_week_start=start, custom_week_end=add_days(start, 6),
				custom_weekly_status="Draft", docstatus=0)).db_insert()
			frappe.get_doc(dict(doctype="Timesheet Detail", name=f"QA-DETAIL-{index:04}", parent=name,
				parenttype="Timesheet", parentfield="time_logs", idx=1, project=self.projects[0], activity_type="Unassigned",
				from_time=get_datetime(start)+timedelta(hours=9), to_time=get_datetime(start)+timedelta(hours=10), hours=1)).db_insert()
		frappe.set_user(self.users[1])
		cursor, names = None, []
		while True:
			page = week.get_team_timesheet_sections(cursor=cursor, filters={"search": "Paging worker"})
			self.assertEqual(page["total"], 505)
			self.assertLessEqual(len(page["rows"]), 50)
			names.extend(row.timesheet for row in page["rows"])
			cursor = page["next_cursor"]
			if not cursor: break
		self.assertEqual(len(names), 505)
		self.assertEqual(len(set(names)), 505)
		frappe.set_user(self.users[0])
		self.assertEqual(week.get_team_timesheet_sections()["total"], 0)
