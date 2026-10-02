"""Five-minute policy through real saves on synthetic qa.local only."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from hrms.api import timer_state as timer, weekly_timesheet as week
from hrms.tests import test_shared_work_state as shared
from hrms.utils.time_overlap import overlap_seconds


class TestOverlapTolerance(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		shared.TestSharedWorkState.setUpClass()
		cls.users = shared.TestSharedWorkState.users
		cls.employees = shared.TestSharedWorkState.employees
		cls.projects = shared.TestSharedWorkState.projects

	setUp = shared.TestSharedWorkState.setUp
	tearDown = shared.TestSharedWorkState.tearDown
	act = shared.TestSharedWorkState.act
	draft = shared.TestSharedWorkState.draft

	def log(self, start, end, project=None):
		return dict(project=project or self.projects[0], activity_type="Unassigned",
			from_time="2026-09-28 " + start, to_time="2026-09-28 " + end)

	def save(self, logs):
		data = week.get_weekly_timesheet(week_start="2026-09-27")
		data["time_logs"] = logs
		return week.save_weekly_timesheet(data)

	def test_exactly_five_minutes_saves_without_changing_intervals(self):
		logs = [self.log("09:00:00", "10:00:00"), self.log("09:55:00", "10:30:00", self.projects[1])]
		result = self.save(logs)
		self.assertEqual(len(result["overlap_warnings"]), 2)
		self.assertEqual(result["time_logs"][1]["from_time"], logs[1]["from_time"])
		self.assertEqual(frappe.db.count("Timesheet Detail", {"parent": result["name"]}), 2)

	def test_five_minutes_and_one_second_rejects_real_save(self):
		before = self.draft()
		with self.assertRaises(frappe.ValidationError):
			self.save([self.log("09:00:00", "10:00:00"), self.log("09:54:59", "10:30:00")])
		self.assertEqual(frappe.db.count("Timesheet Detail", {"parent": before["name"]}), 1)

	def test_separate_small_overlaps_cannot_exceed_total_budget(self):
		with self.assertRaises(frappe.ValidationError):
			self.save([self.log("09:00:00", "09:04:00"), self.log("09:10:00", "09:14:00"), self.log("09:00:00", "09:14:00")])

	def test_union_does_not_count_the_same_minute_twice(self):
		start = datetime(2026, 9, 28, 9)
		self.assertEqual(overlap_seconds(start, start + timedelta(minutes=10), [
			(start, start + timedelta(minutes=4)), (start + timedelta(minutes=2), start + timedelta(minutes=5))]), 300)

	def test_subminute_jitter_is_accepted_by_framework_save(self):
		result = self.save([self.log("09:00:00", "10:00:37"), self.log("10:00:00", "10:30:00")])
		self.assertTrue(result["overlap_warnings"])

	def test_external_document_remains_in_overlap_scope(self):
		first = self.draft()
		doc = frappe.get_doc("Timesheet", first["name"])
		doc.name = "not-the-stored-parent"
		row = frappe._dict(idx=1, from_time="2026-09-28 09:54:59", to_time="2026-09-28 10:30:00")
		doc.time_logs = [row]
		with self.assertRaises(frappe.ValidationError): week.validate_weekly_overlap(doc, row)
		row.from_time = "2026-09-28 09:55:00"
		week.validate_weekly_overlap(doc, row)

	def test_nonweekly_framework_rules_are_unchanged(self):
		from erpnext.projects.doctype.timesheet.timesheet import Timesheet
		from hrms.overrides.employee_timesheet import EmployeeTimesheet
		doc = EmployeeTimesheet(dict(doctype="Timesheet", custom_is_weekly=0))
		with patch.object(Timesheet, "validate_overlap") as original:
			doc.validate_overlap(frappe._dict())
			original.assert_called_once()

	def test_timer_short_overlap_saves_and_replay_is_idempotent(self):
		self.act("start", {"project": self.projects[0]})
		self.now += timedelta(minutes=10)
		self.act("pause")
		state = timer.get_state()
		start = timer._date(state["timer"]["segments"][0]["from"]).astimezone(timer.ZoneInfo(timer.get_system_timezone())).replace(tzinfo=None)
		data = week.get_weekly_timesheet(week_start="2026-09-27")
		data["time_logs"] = [dict(project=self.projects[1], activity_type="Unassigned", from_time=start-timedelta(minutes=10), to_time=start+timedelta(minutes=5))]
		week.save_weekly_timesheet(data)
		saved = self.act("save", {"project": self.projects[0]}, operation="tolerant_save")
		self.assertTrue(saved["overlap_warnings"])
		self.assertFalse(saved["timer"]["segments"])
		timer.apply_action("save", state["revision"], "tolerant_save", {"project": self.projects[0]})
		self.assertEqual(frappe.db.count("Timesheet Detail", {"parent": saved["saved_timesheets"][0]}), 2)

	def test_shared_timer_saves_in_server_timezone_not_browser_timezone(self):
		with patch.object(timer, "get_system_timezone", return_value="EST"):
			self.act("start", {"project": self.projects[0]})
			self.now += timedelta(minutes=10)
			saved = self.act("save", {"project": self.projects[0]})
		row = frappe.get_doc("Timesheet", saved["saved_timesheets"][0]).time_logs[0]
		self.assertEqual(str(row.from_time), "2026-10-02 04:00:00")
		self.assertEqual(str(row.to_time), "2026-10-02 04:10:00")

	def test_legacy_naive_browser_time_cannot_create_wrong_zone_rows(self):
		from hrms.api import save_timer_log
		with self.assertRaises(frappe.ValidationError):
			save_timer_log(self.employees[0], "2026-10-02 13:00:00", "2026-10-02 13:10:00", 1/6, project=self.projects[0])
		self.assertFalse(frappe.db.exists("Timesheet", {"employee": self.employees[0]}))

	def test_legacy_explicit_browser_offset_is_converted_once(self):
		from hrms.api import save_timer_log
		with patch("frappe.utils.get_system_timezone", return_value="EST"):
			name = save_timer_log(self.employees[0], "2026-10-02T13:00:00+04:00", "2026-10-02T13:10:00+04:00", 1/6, project=self.projects[0])
		row = frappe.get_doc("Timesheet", name).time_logs[0]
		self.assertEqual(str(row.from_time), "2026-10-02 04:00:00")
		self.assertEqual(str(row.to_time), "2026-10-02 04:10:00")
