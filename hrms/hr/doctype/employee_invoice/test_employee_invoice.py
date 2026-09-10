from types import SimpleNamespace

from hrms.api.employee_invoice import _calculate_amounts, _hash, _leave_totals
from hrms.tests.utils import HRMSTestSuite


class TestEmployeeInvoice(HRMSTestSuite):
	def test_fixed_monthly_amount_with_adjustments(self):
		rows = [
			SimpleNamespace(adjustment_type="Bonus", effect="Addition", quantity=2, unit_amount=50, note="Bonus"),
			SimpleNamespace(adjustment_type="Prepayment", effect="Deduction", quantity=1, unit_amount=25, note="Advance"),
		]
		base, additions, deductions, total, payable_hours, leave_deduction = _calculate_amounts(
			"Fixed Monthly", 120, 1000, 10, rows
		)
		self.assertEqual(
			(base, additions, deductions, total, payable_hours, leave_deduction),
			(1000, 100, 25, 1075, 0, 0),
		)

	def test_hourly_amount_has_no_hours_cap(self):
		result = _calculate_amounts("Hourly", 260.5, 0, 12.5, [])
		self.assertEqual(result, (3256.25, 0, 0, 3256.25, 260.5, 0))

	def test_fixed_monthly_unpaid_leave_is_prorated(self):
		result = _calculate_amounts(
			"Fixed Monthly",
			120,
			1000,
			10,
			[],
			due_hours=160,
			unpaid_leave_hours=8,
		)
		self.assertEqual(result, (1000, 0, 50, 950, 152, 50))

	def test_hourly_paid_and_sick_leave_are_payable(self):
		result = _calculate_amounts(
			"Hourly",
			120,
			0,
			12.5,
			[],
			paid_leave_hours=8,
			sick_leave_hours=4,
			unpaid_leave_hours=8,
		)
		self.assertEqual(result, (1650, 0, 0, 1650, 132, 0))

	def test_leave_totals_keep_leave_types_separate(self):
		rows = [
			{"leave_type": "Paid Leave", "hours": 8},
			{"leave_type": "Paid Leave", "hours": 4},
			{"leave_type": "Sick Leave", "hours": 1},
			{"leave_type": "Unpaid Leave", "hours": 8},
		]
		self.assertEqual(
			_leave_totals(rows),
			{"Paid Leave": 12, "Sick Leave": 1, "Unpaid Leave": 8},
		)

	def test_material_hash_is_order_independent_for_mapping_keys(self):
		self.assertEqual(_hash({"period": "2026-08", "hours": 184}), _hash({"hours": 184, "period": "2026-08"}))
