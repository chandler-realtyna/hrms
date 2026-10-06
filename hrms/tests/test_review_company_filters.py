"""Standalone checks that company choices respect normal permission queries."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest


class CompanyFilterScopeTest(unittest.TestCase):
	def setUp(self):
		self.calls = []
		self.manager = True
		self.read = True
		frappe = types.ModuleType("frappe")
		frappe.whitelist = lambda: lambda fn: fn
		frappe.session = types.SimpleNamespace(user="hr@example.invalid")
		frappe.PermissionError = PermissionError
		frappe.throw = lambda message, error: (_ for _ in ()).throw(error(message))
		frappe.has_permission = lambda *args: self.read
		def get_list(doctype, **kwargs):
			self.calls.append((doctype, kwargs))
			if doctype == "Company":
				return [types.SimpleNamespace(name="Visible company")]
			return [types.SimpleNamespace(name="EMP-visible", company="Visible company")]
		frappe.get_list = get_list
		personal = types.ModuleType("hrms.utils.personal_scope")
		personal._is_manager = lambda user: self.manager
		self.saved = {name: sys.modules.get(name) for name in ["frappe", "hrms.utils.personal_scope"]}
		sys.modules.update({"frappe": frappe, "hrms.utils.personal_scope": personal})
		path = Path(__file__).parents[1] / "api" / "review_company_filters.py"
		spec = importlib.util.spec_from_file_location("company_scope_under_test", path)
		self.module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.module)

	def tearDown(self):
		for name, value in self.saved.items():
			if value is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = value

	def test_only_permission_scoped_queries_and_visible_company_employees(self):
		result = self.module.get_review_companies("Employee Schedule")
		self.assertEqual(result["employee_companies"], {"EMP-visible": "Visible company"})
		self.assertEqual(self.calls[1][1]["filters"], {"company": ["in", ["Visible company"]]})
		self.assertTrue(all("ignore_permissions" not in kwargs for _, kwargs in self.calls))

	def test_non_manager_and_unrelated_doctype_do_not_query(self):
		self.manager = False
		with self.assertRaises(PermissionError):
			self.module.get_review_companies("Employee Schedule")
		self.manager = True
		with self.assertRaises(PermissionError):
			self.module.get_review_companies("User")
		self.assertEqual(self.calls, [])

	def test_document_read_permission_required(self):
		self.read = False
		with self.assertRaises(PermissionError):
			self.module.get_review_companies("Expense Claim")
		self.assertEqual(self.calls, [])


if __name__ == "__main__":
	unittest.main()
