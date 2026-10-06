"""Scoped SQL ordering and keyset tests on synthetic data, never production."""
import base64
import json
import unittest
from datetime import timedelta

import frappe
from frappe.utils import add_days, get_datetime

from hrms.api import team_timesheets as queue
from hrms.tests import test_shared_work_state as fixtures


class TestTeamQueueOrder(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fixtures.TestSharedWorkState.setUpClass.__func__(cls)

	setUp = fixtures.TestSharedWorkState.setUp
	tearDown = fixtures.TestSharedWorkState.tearDown

	def seed(self):
		frappe.set_user("Administrator")
		self.expected = []
		for index in range(90):
			start = add_days("2026-09-27", -7 * index)
			status = "Pending" if index < 34 else ["Draft", "Returned", "HR Review", "Approved"][index % 4]
			final = index >= 80
			weekly = "Closed" if final else "Pending Project Approval" if status == "Pending" else {
				"Draft": "Draft", "Returned": "Correction Required", "HR Review": "Pending HR Review", "Approved": "Pending HR Review",
			}[status]
			name = f"QA-ORDER-{index:04}"
			modified = get_datetime("2026-10-02 09:00:00") - timedelta(minutes=index // 3)
			submitted = get_datetime(start) + timedelta(days=6, hours=12)
			frappe.get_doc(dict(doctype="Timesheet", name=name, employee=self.employees[0],
				employee_name="Queue ordering worker", company="_Test Company", custom_is_weekly=1,
				custom_week_key=f"{self.employees[0]}|{start}", custom_week_start=start, custom_week_end=add_days(start, 6),
				custom_weekly_status=weekly, custom_weekly_submitted_at=submitted, docstatus=int(final))).db_insert()
			frappe.db.set_value("Timesheet", name, "modified", modified, update_modified=False)
			for project_index, project in enumerate(self.projects):
				frappe.get_doc(dict(doctype="Timesheet Detail", name=f"QA-ORDER-D-{index}-{project_index}", parent=name,
					parenttype="Timesheet", parentfield="time_logs", idx=project_index + 1, project=project, activity_type="Unassigned",
					from_time=get_datetime(start) + timedelta(hours=9), to_time=get_datetime(start) + timedelta(hours=10), hours=1)).db_insert()
				frappe.get_doc(dict(doctype="Timesheet Project Approval", name=f"QA-ORDER-A-{index}-{project_index}", parent=name,
					parenttype="Timesheet", parentfield="custom_project_approvals", idx=project_index + 1, project=project, status=status)).db_insert()
				self.expected.append(dict(timesheet=name, project=project, week_start=str(start), modified=str(modified),
					submitted_at=str(submitted), project_status=status, final=final, actionable=not final and status == "Pending"))
		frappe.set_user(self.users[1])

	def pages(self, view="current", filters=None):
		cursor, rows = None, []
		while True:
			page = queue.get_sections(view, cursor, filters)
			self.assertEqual(set(page), {"rows", "total", "next_cursor"})
			self.assertLessEqual(len(page["rows"]), 50)
			rows.extend(page["rows"])
			self.assertTrue(all(not any(key.startswith("_") for key in row) for row in page["rows"]))
			cursor = page["next_cursor"]
			if not cursor:
				self.assertEqual(len(rows), page["total"])
				return rows

	def expected_order(self, final=False):
		rows = [row for row in self.expected if (row["final"] or row["project_status"] in {"Approved", "HR Review"}) == final]
		rows.sort(key=lambda r: (r["timesheet"], r["project"]), reverse=True)
		rows.sort(key=lambda r: r["modified"], reverse=True)
		if final:
			rows.sort(key=lambda r: r["week_start"], reverse=True)
			return rows
		pending = [r for r in rows if r["actionable"]]
		pending.sort(key=lambda r: (r["week_start"], r["submitted_at"]))
		return pending + [r for status in ("Draft", "Returned", "HR Review", "Approved") for r in rows if r["project_status"] == status]

	def test_disabled_account_moves_unfinished_records_to_history(self):
		self.seed()
		user = frappe.db.get_value("Employee", self.employees[0], "user_id")
		self.assertTrue(user)
		frappe.db.set_value("User", user, "enabled", 0)
		filters = {"employee": self.employees[0]}
		self.assertEqual(queue.get_sections("current", filters=filters)["total"], 0)
		history = queue.get_sections("history", filters=filters)
		self.assertEqual(history["total"], len(self.expected))
		self.assertTrue(all(row.inactive_employee and not row.actionable for row in history["rows"]))
		self.assertTrue(all("inactive" in row.selection_reason for row in history["rows"]))

	def test_mixed_order_all_pages_ties_and_filters(self):
		self.seed()
		rows = self.pages()
		identity = lambda r: (r["timesheet"], r["project"])
		self.assertEqual([identity(r) for r in rows], [identity(r) for r in self.expected_order()])
		self.assertEqual(len({identity(r) for r in rows}), 112)
		self.assertTrue(all(r.actionable for r in rows[:68]))
		for status in ("Pending", "Draft", "Returned", "HR Review", "Approved"):
			filtered = self.pages(filters={"status": status, "search": "Queue ordering"})
			self.assertEqual([identity(r) for r in filtered], [identity(r) for r in self.expected_order() if r["project_status"] == status])
		self.assertEqual([identity(r) for r in self.pages("history")], [identity(r) for r in self.expected_order(True)])
		self.assertTrue(all(not r.actionable for r in self.pages("history")))

	def test_scope_applies_before_order_count_and_cursor(self):
		self.seed()
		frappe.db.set_value("Project", self.projects[1], "custom_project_lead", self.employees[0])
		self.assertEqual(len(self.pages()), 56)
		self.assertTrue(all(r.project == self.projects[0] for r in self.pages()))
		frappe.set_user(self.users[2])
		self.assertEqual(len(self.pages()), 112)
		frappe.set_user(self.users[0])
		self.assertEqual(queue.get_sections()["total"], 0)

	def test_history_pagination_uses_week_not_recent_modification(self):
		self.seed()
		for row in self.expected:
			if int(row["timesheet"].rsplit("-", 1)[1]) >= 34:
				row["final"] = True
				frappe.db.set_value("Timesheet", row["timesheet"], {"custom_weekly_status": "Closed", "docstatus": 1}, update_modified=False)
		rows = self.pages("history")
		self.assertEqual(len(rows), 112)
		self.assertEqual([(r.timesheet, r.project) for r in rows], [(r["timesheet"], r["project"]) for r in self.expected_order(True)])

	def test_old_invalid_and_different_context_cursors_require_reset(self):
		self.seed()
		cursor = queue.get_sections()["next_cursor"]
		self.assertEqual(len(queue.get_sections(cursor=cursor, filters={"search": "", "status": ""})["rows"]), 50)
		old = base64.urlsafe_b64encode(json.dumps(["2026-10-02", "TS-OLD", self.projects[0]]).encode()).decode()
		for invalid in (old, "not-base64", base64.urlsafe_b64encode(b"{}").decode()):
			with self.assertRaises(queue.TeamCursorResetRequired): queue.get_sections(cursor=invalid)
		with self.assertRaises(queue.TeamCursorResetRequired): queue.get_sections(cursor=cursor, filters={"status": "Draft"})
		with self.assertRaises(queue.TeamCursorResetRequired): queue.get_sections("history", cursor)
		frappe.set_user(self.users[2])
		with self.assertRaises(queue.TeamCursorResetRequired): queue.get_sections(cursor=cursor)
