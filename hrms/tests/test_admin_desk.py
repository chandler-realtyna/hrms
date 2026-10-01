import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from hrms.api.admin_desk import _admin_desk_sections, set_admin_reviews_home


class TestAdminDesk(unittest.TestCase):
	def test_sidebar_sections_support_native_expand_events(self):
		sections = [{"label": "Timesheet Reviews", "items": [{"label": "Project Timesheets", "route": "/desk/admin-reviews/project-timesheets"}]}]
		boot = frappe._dict(docs=[], workspace_sidebar_item={})
		page = frappe._dict(name="admin-reviews", doctype="Page")
		with patch("hrms.api.admin_desk._admin_desk_sections", return_value=sections), patch("frappe.desk.desk_page.get", return_value=page), patch.object(frappe, "session", SimpleNamespace(user="manager@example.test")):
			set_admin_reviews_home(boot)
		items = boot.workspace_sidebar_item["admin reviews"]["items"]
		self.assertTrue(all(item["collapsible"] for item in items if item["type"] == "Section Break"))
		self.assertEqual(items[-1]["link_type"], "Page")
		self.assertEqual(items[-1]["link_to"], "admin-reviews/project-timesheets")
		self.assertEqual(boot.home_page, "admin-reviews")

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
		self.assertIn("Leave Requests", labels)
		self.assertIn("Expense Requests", labels)

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
						{"label": "Project Timesheets", "route": "/desk/admin-reviews/project-timesheets"}
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
				"Leave Requests",
				"Expense Requests",
				"Holiday Approvals",
				"Schedule Approvals",
				"Employee Invoices",
				"Users",
				"Employees",
				"Projects",
			},
		)
		self.assertTrue(all(item["route"].startswith("/desk/") for section in sections for item in section["items"]))
