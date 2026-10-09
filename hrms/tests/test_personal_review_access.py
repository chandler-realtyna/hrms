"""Standalone permission and rejected holiday resubmission regression checks."""
import ast
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1]


class PersonalReviewTest(unittest.TestCase):
	def setUp(self):
		self.calls = []
		self.deny = None
		self.saved = sys.modules.get("frappe")
		self.frappe = types.ModuleType("frappe")
		self.frappe.PermissionError = PermissionError
		self.frappe.throw = lambda message, *args: (_ for _ in ()).throw(PermissionError(message))
		def get_doc(doctype, name):
			self.calls.append((doctype, name))
			def check(permission):
				self.calls.append((doctype, permission))
				if self.deny == doctype:
					raise PermissionError("Denied")
			return types.SimpleNamespace(employee="EMP-1", company="Company A", check_permission=check)
		self.frappe.get_doc = get_doc
		sys.modules["frappe"] = self.frappe
		self.scope = {}
		exec(compile((ROOT / "utils/personal_review_access.py").read_text(), "personal_review_access.py", "exec"), self.scope)

	def tearDown(self):
		if self.saved is None:
			sys.modules.pop("frappe", None)
		else:
			sys.modules["frappe"] = self.saved

	def test_review_requires_document_employee_and_company_permission(self):
		self.scope["get_personal_review_doc"]("Employee Holiday", "HOL-1", "write")
		self.assertIn(("Employee Holiday", "write"), self.calls)
		self.assertIn(("Employee", "read"), self.calls)
		self.assertIn(("Company", "read"), self.calls)
		for doctype in ["Employee Holiday", "Employee", "Company"]:
			self.deny = doctype
			with self.assertRaises(PermissionError):
				self.scope["get_personal_review_doc"]("Employee Holiday", "HOL-1", "write")

	def test_all_six_review_apis_use_permission_gate(self):
		tree = ast.parse((ROOT / "api/__init__.py").read_text())
		functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
		for name in ["approve_employee_holiday", "reject_employee_holiday", "get_holiday_approval_detail", "approve_employee_schedule", "reject_employee_schedule", "get_schedule_approval_detail"]:
			calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get_personal_review_doc"]
			self.assertEqual(len(calls), 1, name)
			self.assertEqual(calls[0].args[2].value, "read" if name.startswith("get_") else "write")

	def test_rejected_holiday_resubmits_with_partial_allowance(self):
		tree = ast.parse((ROOT / "api/__init__.py").read_text())
		fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "submit_employee_holidays")
		fn.decorator_list = []
		module = ast.Module(body=[fn], type_ignores=[])
		for status in ["Draft", "Rejected", "Submitted", "Approved"]:
			for count in [0, 1, 14, 15, 16]:
				doc = types.SimpleNamespace(employee="EMP-1", status=status, holidays=[{}] * count, save=lambda **kwargs: None, as_dict=lambda: {"status": "Submitted"})
				self.frappe.get_doc = lambda *args: doc
				scope = {"frappe": self.frappe, "_": lambda value: value, "_get_employee_for_user": lambda: "EMP-1", "_is_hr_or_admin": lambda: False}
				exec(compile(module, "holiday_submit", "exec"), scope)
				if status in {"Draft", "Rejected"} and 1 <= count <= 15:
					scope["submit_employee_holidays"]("HOL-1")
					self.assertEqual(doc.status, "Submitted")
				else:
					with self.assertRaises(PermissionError):
						scope["submit_employee_holidays"]("HOL-1")


if __name__ == "__main__":
	unittest.main()
