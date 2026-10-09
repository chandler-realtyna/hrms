import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from hrms.utils import company_desk as scope


def user(roles=(), archive=None):
	doc = frappe._dict(name="manager@example.test", roles=[frappe._dict(role=role) for role in roles])
	doc.meta = SimpleNamespace(has_field=lambda field: True)
	doc[scope.ARCHIVE_FIELD] = json.dumps(archive) if archive else None
	doc.db_set = MagicMock()
	return doc


class TestDirectorScope(unittest.TestCase):
	def test_ordinary_employee_scope_is_untouched(self):
		with patch.object(frappe, "get_all") as read, patch.object(frappe, "delete_doc") as delete:
			scope.sync_director_scope(user(["Employee"]))
		read.assert_not_called()
		delete.assert_not_called()

	def test_only_director_scope_filters_are_archived_and_removed(self):
		rule = frappe._dict(name="scope-test", allow="Employee", for_value="EMP-TEST", applicable_for=None, apply_to_all_doctypes=1)
		doc = user([scope.ROLE])
		with patch.object(frappe, "get_all", return_value=[rule]) as read, patch.object(frappe, "delete_doc") as delete, patch.object(frappe, "clear_cache"):
			scope.sync_director_scope(doc)
		self.assertEqual(read.call_args.kwargs["filters"]["allow"], ("in", scope.SCOPE_TYPES))
		self.assertEqual(json.loads(doc.db_set.call_args.args[1])[0]["for_value"], "EMP-TEST")
		delete.assert_called_once_with("User Permission", "scope-test", ignore_permissions=True)

	def test_recreated_scope_does_not_duplicate_archive(self):
		rule = frappe._dict(name="new-scope", allow="Employee", for_value="EMP-TEST", applicable_for=None, apply_to_all_doctypes=1)
		doc = user([scope.ROLE], [dict(rule)])
		with patch.object(frappe, "get_all", return_value=[rule]), patch.object(frappe, "delete_doc"), patch.object(frappe, "clear_cache"):
			scope.sync_director_scope(doc)
		self.assertEqual(len(json.loads(doc.db_set.call_args.args[1])), 1)

	def test_scope_is_restored_when_director_role_is_revoked(self):
		rule = {"allow": "Employee", "for_value": "EMP-TEST", "apply_to_all_doctypes": 1}
		doc = user(["Employee"], [rule])
		restored = MagicMock()
		with patch.object(frappe.db, "exists", side_effect=[True, False]), patch.object(frappe, "get_doc", return_value=restored), patch.object(frappe, "clear_cache"):
			scope.sync_director_scope(doc)
		restored.insert.assert_called_once_with(ignore_permissions=True)
		doc.db_set.assert_called_once_with(scope.ARCHIVE_FIELD, None, update_modified=False)
