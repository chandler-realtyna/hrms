import unittest
from unittest.mock import patch

from hrms.api.admin_desk import _admin_desk_sections


class TestAdminDesk(unittest.TestCase):
	@patch("hrms.api.admin_desk._is_approver", return_value=False)
	@patch("hrms.api.weekly_timesheet.is_project_manager", return_value=False)
	@patch("hrms.api.weekly_timesheet.is_project_lead", return_value=False)
	@patch("hrms.api.admin_desk.frappe.has_permission")
	@patch("hrms.api.admin_desk.frappe.get_roles", return_value=["HR Manager"])
	def test_hr_sections_include_only_permitted_admin_workflows(
		self, _roles, has_permission, _lead, _manager, _approver
	):
		has_permission.side_effect = lambda doctype, permission: (
			doctype in {"User", "Employee", "Project"}
			and permission in {"read", "create", "write"}
		)

		sections = _admin_desk_sections()
		labels = {item["label"] for section in sections for item in section["items"]}

		self.assertIn("Holiday Approvals", labels)
		self.assertIn("Schedule Approvals", labels)
		self.assertIn("Employee Invoices", labels)
		self.assertIn("Users", labels)
		self.assertIn("Employees", labels)
		self.assertIn("Projects", labels)
		self.assertIn("Leave and Expense Requests", labels)

	@patch("hrms.api.admin_desk._is_approver", return_value=False)
	@patch("hrms.api.weekly_timesheet.is_project_manager", return_value=False)
	@patch("hrms.api.weekly_timesheet.is_project_lead", return_value=True)
	@patch("hrms.api.admin_desk.frappe.has_permission", return_value=False)
	@patch("hrms.api.admin_desk.frappe.get_roles", return_value=["Employee"])
	def test_project_lead_sees_only_own_review_entry(
		self, _roles, _has_permission, _lead, _manager, _approver
	):
		sections = _admin_desk_sections()

		self.assertEqual(
			sections,
			[
				{
					"label": "Timesheet Reviews",
					"items": [
						{"label": "Project Timesheets", "route": "/hrms/project-timesheets"}
					],
				}
			],
		)

	@patch("hrms.api.admin_desk._is_approver", return_value=False)
	@patch("hrms.api.weekly_timesheet.is_project_manager", return_value=False)
	@patch("hrms.api.weekly_timesheet.is_project_lead", return_value=False)
	@patch("hrms.api.admin_desk.frappe.has_permission", return_value=True)
	@patch(
		"hrms.api.admin_desk.frappe.get_roles",
		return_value=["HR Manager", "Company Desk Administrator"],
	)
	def test_company_director_sees_every_admin_section(
		self, _roles, _has_permission, _lead, _manager, _approver
	):
		sections = _admin_desk_sections()
		labels = {item["label"] for section in sections for item in section["items"]}

		self.assertEqual(
			labels,
			{
				"Project Timesheets",
				"Project Weekly Reports",
				"HR Weekly Timesheet Review",
				"Leave and Expense Requests",
				"Holiday Approvals",
				"Schedule Approvals",
				"Employee Invoices",
				"Users",
				"Employees",
				"Projects",
			},
		)
