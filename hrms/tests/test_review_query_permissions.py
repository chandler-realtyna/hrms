"""Native permission conditions remain in SQL and known-document HR access."""
import ast
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).parents[1]

class TestReviewQueryPermissions(unittest.TestCase):
 def load(self, hr=True, readable=True, condition=' and (`tabTimesheet`.`company` = \'A\' and `tabTimesheet`.`employee` = \'E\')'):
  def throw(*args): raise PermissionError(args[0])
  modules={
   'frappe':NS(_=lambda x:x, has_permission=lambda *args:readable, throw=throw,PermissionError=PermissionError),
   'frappe.desk.reportview':NS(get_match_cond=lambda doctype:condition),
   'hrms.api.weekly_timesheet':NS(_is_hr=lambda:hr),
  }
  spec=importlib.util.spec_from_file_location('review_permissions_fixture', ROOT/'utils/review_query_permissions.py')
  module=importlib.util.module_from_spec(spec)
  with patch.dict(sys.modules,modules):spec.loader.exec_module(module)
  return module,modules
 def test_native_company_and_employee_conditions_preserved_with_alias(self):
  module,modules=self.load()
  with patch.dict(sys.modules,modules):result=module.hr_read_condition('Timesheet','t')
  self.assertEqual(result,"(`t`.`company` = 'A' and `t`.`employee` = 'E')")
 def test_no_read_denied_not_unrestricted_sql(self):
  module,modules=self.load(readable=False)
  with patch.dict(sys.modules,modules),self.assertRaises(PermissionError):module.hr_read_condition('Timesheet','t')
 def test_delegated_lead_scope_not_replaced_by_native_own_list_hook(self):
  module,modules=self.load(hr=False,readable=False)
  with patch.dict(sys.modules,modules):self.assertEqual(module.hr_read_condition('Timesheet','t'),'')
 def test_alias_cannot_inject_sql(self):
  module,modules=self.load()
  with patch.dict(sys.modules,modules),self.assertRaises(PermissionError):module.hr_read_condition('Timesheet','t OR 1=1')
 def test_known_document_permission_failure_prevents_project_access(self):
  module,modules=self.load()
  calls=[]
  def denied(permission): calls.append(permission);raise PermissionError()
  modules['frappe'].get_doc=lambda *args:self.fail('Project accessed after denied Timesheet')
  with patch.dict(sys.modules,modules),self.assertRaises(PermissionError):
   module.check_hr_review_permission(NS(check_permission=denied,time_logs=[]),'write')
  self.assertEqual(calls,['write'])
 def test_project_read_permissions_apply_to_hr_and_lead_delegation_unchanged(self):
  module,modules=self.load();calls=[]
  modules['frappe'].get_doc=lambda doctype,name:NS(check_permission=lambda p:calls.append((doctype,name,p)))
  doc=NS(check_permission=lambda p:calls.append(('Timesheet',p)),time_logs=[NS(project='P')])
  with patch.dict(sys.modules,modules):module.check_hr_review_permission(doc,'write')
  self.assertEqual(calls,[('Timesheet','write'),('Project','P','read')])
  modules['hrms.api.weekly_timesheet']._is_hr=lambda:False
  with patch.dict(sys.modules,modules):module.check_hr_review_permission(doc,'write')
  self.assertEqual(len(calls),2)
 def test_known_document_endpoints_stop_at_denied_hr_permission(self):
  tree=ast.parse((ROOT/'api/weekly_timesheet.py').read_text())
  cases={
   'get_project_review_detail': ('P','2026-10-04','E'),
   'get_timesheet_review_detail': ('TS',),
   'review_saved_project_entries': ('TS','P','v1',None,'approve','Reason'),
   'reset_project_review': ('TS','P','v1','Reason'),
   'return_timesheet_entries': ('TS',['entry'],'Reason','hr'),
   'reopen_weekly_timesheet': ('TS','v1','Reason'),
   'hr_return_weekly_timesheet': ('TS','Reason'),
   'hr_close_weekly_timesheet': ('TS',),
  }
  for name,args in cases.items():
   with self.subTest(name=name):
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);node.decorator_list=[]
    calls=[]
    def deny(doc,permission='read',**kwargs): calls.append(permission);raise PermissionError('restricted')
    frappe=NS(get_doc=lambda *a:NS(),db=NS(sql=lambda *a:None,get_value=lambda *a:'TS'),parse_json=lambda x:x,session=NS(user='hr'))
    env=dict(frappe=frappe,_=lambda x:x,_require_hr=lambda:None,_is_hr=lambda:True,_project_lead_user=lambda p:'lead',_project_manager_user=lambda p:'manager',getdate=lambda x:x,check_hr_review_permission=deny)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(ROOT/'api/weekly_timesheet.py'),'exec'),env)
    with self.assertRaisesRegex(PermissionError,'restricted'):env[name](*args)
    self.assertEqual(calls,['read' if name.startswith('get_') else 'write'])
 def test_direct_endpoints_gate_before_routing_save_or_serialization(self):
  tree=ast.parse((ROOT/'api/weekly_timesheet.py').read_text())
  functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
  for name in ['get_project_review_detail','get_timesheet_review_detail','review_saved_project_entries','reset_project_review','return_timesheet_entries','reopen_weekly_timesheet','hr_return_weekly_timesheet','hr_close_weekly_timesheet']:
   node=functions[name]; source=ast.get_source_segment((ROOT/'api/weekly_timesheet.py').read_text(),node)
   self.assertIn('check_hr_review_permission(doc,',source,name)
   gate=source.index('check_hr_review_permission(doc,')
   for operation in ['_refresh_review_routing(doc)','_serialize_weekly(doc)','doc.save(ignore_permissions=True)']:
    if operation in source:self.assertLess(gate,source.index(operation),name)

if __name__=='__main__':unittest.main()
