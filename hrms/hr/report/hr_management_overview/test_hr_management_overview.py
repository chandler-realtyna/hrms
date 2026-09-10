from unittest import TestCase

from hrms.hr.report.hr_management_overview.hr_management_overview import _demo_data


class TestHRManagementOverview(TestCase):
	def test_demo_data_covers_management_workflows(self):
		rows, summary, chart = _demo_data()

		metrics = {row["metric"] for row in rows}
		self.assertIn("Draft timesheets", metrics)
		self.assertIn("Pending leave requests", metrics)
		self.assertIn("Unpaid expense claims", metrics)
		self.assertIn("Pending HR Review", metrics)
		self.assertIn("Approved for Payment", metrics)
		self.assertIn("Paid", metrics)
		self.assertEqual(len(summary), 4)
		self.assertEqual(chart["type"], "bar")
