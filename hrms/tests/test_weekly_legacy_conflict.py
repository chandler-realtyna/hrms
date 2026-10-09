"""Database-free regression tests for versionless cached-client save safety."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

source = Path(__file__).parents[1] / 'api' / 'weekly_timesheet.py'
tree = ast.parse(source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'_serialize_row', '_legacy_draft_is_additive'}]
namespace = {'flt': lambda value, precision=4: round(float(value or 0), precision), 'cint': lambda value: int(value or 0), 'get_datetime': lambda value: datetime.fromisoformat(str(value))}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
check = namespace['_legacy_draft_is_additive']
serialize = namespace['_serialize_row']

class TestLegacyConflict(unittest.TestCase):
    def setUp(self):
        self.row = SimpleNamespace(name='ROW', project='P', activity_type='Support', description='Task', from_time=datetime(2026, 9, 28, 9, 30), to_time=datetime(2026, 9, 28, 9, 42), hours=0.2, is_billable=0)
        self.row.get = lambda key: getattr(self.row, key, None)
        self.doc = SimpleNamespace(name='TS', note=None, time_logs=[self.row])
        self.payload = {'name': 'TS', 'time_logs': [serialize(self.row)]}

    def test_unchanged_and_additive_legacy_payloads(self):
        self.assertTrue(check(self.doc, self.payload))
        self.payload['time_logs'].append({**serialize(self.row), 'name': None})
        self.assertTrue(check(self.doc, self.payload))

    def test_changed_fields_are_not_overwritten(self):
        for field, value in [('description', 'changed'), ('project', 'other'), ('activity_type', 'other'), ('from_time', '2026-09-28 10:00:00'), ('to_time', '2026-09-28 10:12:00'), ('hours', 5), ('is_billable', 1)]:
            with self.subTest(field=field):
                self.assertFalse(check(self.doc, {**self.payload, 'time_logs': [{**serialize(self.row), field: value}]}))
        self.assertFalse(check(self.doc, {**self.payload, 'note': 'changed'}))

    def test_deletions_duplicates_and_resurrections_are_rejected(self):
        self.assertFalse(check(self.doc, {**self.payload, 'time_logs': []}))
        self.assertFalse(check(self.doc, {**self.payload, 'time_logs': [serialize(self.row)] * 2}))
        self.assertFalse(check(self.doc, {**self.payload, 'time_logs': [serialize(self.row), {**serialize(self.row), 'name': 'deleted'}]}))
        self.assertFalse(check(self.doc, {**self.payload, 'name': None}))

if __name__ == '__main__':
    unittest.main()
