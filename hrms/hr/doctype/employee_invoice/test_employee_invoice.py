from types import SimpleNamespace
from unittest.mock import patch

from hrms.api.employee_invoice import _calculate_amounts, _hash, _leave_totals, get_employee_invoice_review_readiness
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


class TestInvoiceReviewReadiness(HRMSTestSuite):
	def _check(self, doc, rows, ready):
		with patch("hrms.api.employee_invoice._require_hr") as require_hr, patch(
			"hrms.api.employee_invoice._get_doc", return_value=doc
		) as get_doc, patch("hrms.api.employee_invoice._timesheet_rows", return_value=(rows, ready)) as sources:
			result = get_employee_invoice_review_readiness("INV-test")
			require_hr.assert_called_once_with()
			get_doc.assert_called_once_with("INV-test")
			sources.assert_called_once_with(doc.employee, doc.period_start, doc.period_end)
			return result

	def test_current_finalized_sources_override_stale_false_snapshot(self):
		doc = SimpleNamespace(employee="EMP-test", period_start="2026-09-01", period_end="2026-09-30", time_approval_ready=0)
		result = self._check(doc, [{"timesheet": "TS-final", "approval_status": "Finalized"}], True)
		self.assertEqual(result, {"ready": True, "unfinalized_count": 0})
		self.assertEqual(doc.time_approval_ready, 0)

	def test_new_unfinalized_source_blocks_stale_true_snapshot(self):
		doc = SimpleNamespace(employee="EMP-test", period_start="2026-09-01", period_end="2026-09-30", time_approval_ready=1)
		rows = [{"timesheet": "TS-final", "approval_status": "Finalized"}, {"timesheet": "TS-new", "approval_status": "Not finalized"}, {"timesheet": "TS-new", "approval_status": "Not finalized"}]
		self.assertEqual(self._check(doc, rows, False), {"ready": False, "unfinalized_count": 1})
		self.assertEqual(doc.time_approval_ready, 1)

	def test_role_rejection_stops_document_and_source_reads(self):
		with patch("hrms.api.employee_invoice._require_hr", side_effect=PermissionError), patch("hrms.api.employee_invoice._get_doc") as get_doc:
			with self.assertRaises(PermissionError):
				get_employee_invoice_review_readiness("INV-test")
			get_doc.assert_not_called()
