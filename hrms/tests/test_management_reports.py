import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from hrms.api.management_reports import _aggregate, _date_range, _project_scope, get_time_history


def entry(**values):
	return frappe._dict({"name": "row-1", "timesheet": "TS-1", "employee": "E-1", "employee_name": "Person",
		"project": "P-1", "project_label": "Project One", "activity_type": "Development", "hours": 2,
		"from_time": "2026-09-28 09:00:00", "docstatus": 0, "custom_weekly_status": "Draft", **values})


class TestManagementReports(unittest.TestCase):
	def test_recorded_and_closed_hours_are_distinct(self):
		result = _aggregate([entry(), entry(name="row-2", hours=3, docstatus=1, custom_weekly_status="Closed")], "project")
		self.assertEqual(result["totals"]["hours"], 5)
		self.assertEqual(result["totals"]["status_hours"], {"Draft": 2, "Closed": 3})
		self.assertEqual(result["rows"][0]["label"], "Project One")

	def test_groupings_do_not_duplicate_records(self):
		rows = [entry(), entry(name="row-2", employee="E-2", activity_type="Testing", hours=1)]
		for group_by in ("project", "employee", "activity_type", "month"):
			result = _aggregate(rows, group_by)
			self.assertEqual(sum(row["entries"] for row in result["rows"]), 2)
			self.assertEqual(sum(row["hours"] for row in result["rows"]), 3)

	def test_date_range_is_bounded(self):
		for dates in [("2024-01-01", "2026-01-01"), ("2026-09-30", "2026-09-01")]:
			with self.assertRaises(frappe.ValidationError):
				_date_range(*dates)

	@patch("hrms.api.management_reports._is_hr", return_value=True)
	def test_hr_scope_is_company_wide(self, _hr):
		self.assertIsNone(_project_scope())

	@patch("hrms.api.management_reports._is_hr", return_value=False)
	def test_nonmanager_is_denied(self, _hr):
		with patch.object(frappe, "session", SimpleNamespace(user="employee@example.test")), patch("frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.PermissionError):
				_project_scope()

	@patch("hrms.api.management_reports._is_hr", return_value=False)
	def test_historical_scope_includes_closed_projects(self, _hr):
		with patch.object(frappe, "session", SimpleNamespace(user="lead@example.test")), patch("frappe.db.get_value", return_value="E-1"), patch("frappe.get_all", side_effect=[["P-1"], ["P-2"]]) as get_all:
			self.assertEqual(_project_scope(), {"P-1", "P-2"})
			self.assertTrue(all("status" not in call.kwargs["filters"] for call in get_all.call_args_list))

	@patch("hrms.api.management_reports._project_scope", return_value={"P-1"})
	def test_project_filter_cannot_escape_scope(self, _scope):
		with patch("hrms.api.management_reports._read_entries") as read:
			with self.assertRaises(frappe.PermissionError):
				get_time_history(project="P-2")
			read.assert_not_called()

	@patch("hrms.api.management_reports._project_scope", return_value=None)
	def test_filtering_preserves_source_records(self, _scope):
		rows = [entry(), entry(name="closed-row", custom_weekly_status="Closed", docstatus=1)]
		with patch("hrms.api.management_reports._read_entries", return_value=rows), patch("frappe.get_all", return_value=[frappe._dict(name="P-1", project_name="Named project")]):
			result = get_time_history("2026-09-01", "2026-09-30", status="Closed")
			self.assertEqual(result["totals"]["entries"], 1)
			self.assertEqual(result["entries"][0].name, "closed-row")
			self.assertEqual(result["rows"][0]["label"], "Named project")
