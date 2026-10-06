"""Stable employee calendar identities and shared-list mutation protection."""
import ast
from datetime import date
from pathlib import Path
import sys
import types
import unittest


class CalendarIdentityTest(unittest.TestCase):
	def setUp(self):
		self.saved = sys.modules.get("frappe")
		self.checks = []
		self.shared_doctype = None
		self.frappe = types.ModuleType("frappe")
		self.frappe._ = lambda message: message
		self.frappe.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
		self.frappe.get_meta = lambda doctype: types.SimpleNamespace(has_field=lambda field: True)
		def exists(doctype, filters):
			self.checks.append((doctype, filters))
			return doctype == self.shared_doctype
		self.frappe.db = types.SimpleNamespace(exists=exists)
		sys.modules["frappe"] = self.frappe
		self.scope = {}
		path = Path(__file__).parents[1] / "utils/employee_holiday_calendar.py"
		exec(compile(path.read_text(), str(path), "exec"), self.scope)

	def tearDown(self):
		if self.saved is None:
			sys.modules.pop("frappe", None)
		else:
			sys.modules["frappe"] = self.saved

	def test_employee_identity_is_stable_and_distinct_for_same_display_name(self):
		name = self.scope["personal_calendar_name"]
		self.assertNotEqual(name("EMP-1", 2026), name("EMP-2", 2026))
		self.assertEqual(name("EMP-1", "2026"), name("EMP-1", 2026))
		self.assertNotEqual(name("EMP-1", 2026), name("EMP-1", 2027))
		self.assertLessEqual(len(name("E" * 140, 2026)), 140)
		self.assertNotEqual(name("E" * 139 + "1", 2026), name("E" * 139 + "2", 2026))

	def test_shared_employee_assignment_or_company_calendar_blocks_rebuild(self):
		for doctype in ["Employee Holiday", "Holiday List Assignment", "Employee", "Company"]:
			self.shared_doctype = doctype
			with self.assertRaises(ValueError):
				self.scope["ensure_calendar_not_shared"]("Employee holidays - EMP-1 - 2026", "EMP-1")

	def test_unshared_calendar_checks_identity_not_display_name(self):
		self.scope["ensure_calendar_not_shared"]("Employee holidays - EMP-1 - 2026", "EMP-1")
		self.assertEqual(self.checks[0][1]["employee"], ["!=", "EMP-1"])
		self.assertTrue(all("employee_name" not in filters for _, filters in self.checks))

	def test_controller_creates_new_identity_calendar_without_rewriting_legacy_list(self):
		legacy_name = "Same display name - 2026"
		legacy_dates = [{"holiday_date": "2026-01-02", "description": "Historical"}]
		created = {}
		assigned = []
		class Calendar:
			def __init__(calendar):
				calendar.holidays = []
			def append(calendar, field, value):
				calendar.holidays.append(value)
			def save(calendar, **kwargs):
				created[calendar.holiday_list_name] = calendar.holidays
		self.frappe.db.exists = lambda doctype, name: doctype == "Holiday List" and name == legacy_name
		self.frappe.db.set_value = lambda *args, **kwargs: None
		self.frappe.get_doc = lambda *args: (_ for _ in ()).throw(AssertionError("Existing legacy list must not be loaded for rebuild"))
		self.frappe.new_doc = lambda doctype: Calendar()
		policy = types.ModuleType("hrms.hr.leave_policy_setup")
		policy._weekend_dates = lambda year: [date(2026, 1, 3)]
		helper = types.ModuleType("hrms.utils.employee_holiday_calendar")
		helper.personal_calendar_name = self.scope["personal_calendar_name"]
		helper.ensure_calendar_not_shared = self.scope["ensure_calendar_not_shared"]
		modules = {"hrms.hr.leave_policy_setup": policy, "hrms.utils.employee_holiday_calendar": helper}
		previous = {key: sys.modules.get(key) for key in modules}
		sys.modules.update(modules)
		try:
			tree = ast.parse((Path(__file__).parents[1] / "hr/doctype/employee_holiday/employee_holiday.py").read_text())
			controller = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "EmployeeHoliday")
			fn = next(node for node in controller.body if isinstance(node, ast.FunctionDef) and node.name == "_create_holiday_list")
			scope = {"frappe": self.frappe, "getdate": lambda value: value if isinstance(value, date) else date.fromisoformat(value)}
			exec(compile(ast.Module(body=[fn], type_ignores=[]), "calendar_controller", "exec"), scope)
			doc = types.SimpleNamespace(employee="EMP-1", employee_name="Same display name", year=2026, name="HOL-1", holidays=[types.SimpleNamespace(date="2026-01-02", description="Current selection")], _assign_holiday_list=assigned.append)
			scope["_create_holiday_list"](doc)
			self.assertEqual(assigned, ["Employee holidays - EMP-1 - 2026"])
			self.assertEqual(list(created), assigned)
			self.assertEqual(legacy_dates, [{"holiday_date": "2026-01-02", "description": "Historical"}])
		finally:
			for key, value in previous.items():
				if value is None:
					sys.modules.pop(key, None)
				else:
					sys.modules[key] = value


if __name__ == "__main__":
	unittest.main()
