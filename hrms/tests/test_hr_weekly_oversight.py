"""Database-free tests for HR visibility without bypassing final approval."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
path = Path(__file__).parents[1] / 'api' / 'weekly_timesheet.py'
tree = ast.parse(path.read_text())
names = {'get_hr_weekly_timesheet_queue', 'hr_close_weekly_timesheet', '_hr_review_blockers'}
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
for n in nodes: n.decorator_list = []
class TestOversight(unittest.TestCase):
 def setUp(self):
  self.filters = None
  self.docs = [NS(name='WAIT',custom_is_weekly=1,employee='E',employee_name='QA',custom_week_start='2026-09-27',custom_week_end='2026-10-03',total_hours=1,modified='2026-10-01',docstatus=0,custom_weekly_status='Pending Project Approval',custom_weekly_submitted_at='2026-10-01',time_logs=[NS(project='P',from_time='2026-09-28 09:00:00',hours=1,activity_type='Support')],custom_project_approvals=[NS(project='P',status='Pending',controller='lead')]), NS(name='FINAL',custom_is_weekly=1,employee='E',employee_name='QA',custom_week_start='2026-09-20',custom_week_end='2026-09-26',total_hours=1,modified='2026-10-02',docstatus=1,custom_weekly_status='Closed',custom_weekly_submitted_at='2026-09-27',time_logs=[],custom_project_approvals=[])]
  def listing(doctype,filters,**kwargs):
   self.filters=filters
   status=filters['custom_weekly_status']
   return [d for d in self.docs if d.docstatus==filters['docstatus'] and d.custom_weekly_submitted_at and (d.custom_weekly_status in status[1] if isinstance(status,tuple) else d.custom_weekly_status==status)]
  def throw(message,*args): raise ValueError(message)
  self.ns={'frappe':NS(get_list=listing,get_doc=lambda dt,name:next(d for d in self.docs if d.name==name),throw=throw,db=NS(get_value=lambda *a:'QA Lead')), '_':lambda s:s,'_require_hr':lambda:None,'_project_reviews_ready':lambda d:d.custom_weekly_status!='Pending Project Approval','_team_review_blockers':lambda d:[], '_serialize_row':lambda r:{'project':r.project},'get_datetime':__import__('datetime').datetime.fromisoformat,'flt':lambda n:float(n or 0),'_project_display_name':lambda p:'Project '+p,'_hr_employee_image':lambda e:'', 'cint':int, 'PENDING_PROJECT':'Pending Project Approval','CORRECTION_REQUIRED':'Correction Required','PENDING_HR':'Pending HR Review','CLOSED':'Closed','APPROVAL_PENDING':'Pending','APPROVAL_RETURNED':'Returned','APPROVAL_HR':'HR Review','APPROVAL_APPROVED':'Approved'}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),self.ns)
 def test_project_waiting_week_visible_but_not_finalizable(self):
  rows=self.ns['get_hr_weekly_timesheet_queue']()
  self.assertEqual([r['name'] for r in rows],['WAIT'])
  self.assertFalse(rows[0]['ready_for_hr_close'])
  self.assertIn('QA Lead',rows[0]['review_blockers'][0])
  self.assertEqual(rows[0]['activity_types'],['Support'])
  with self.assertRaises(ValueError):self.ns['hr_close_weekly_timesheet']('WAIT')
 def test_history_is_separate_and_locked(self):
  rows=self.ns['get_hr_weekly_timesheet_queue']('history')
  self.assertEqual([r['name'] for r in rows],['FINAL'])
  self.assertFalse(rows[0]['ready_for_hr_close']);self.assertEqual(rows[0]['review_blockers'],[])
 def test_ready_requires_both_stage_and_completed_reviews(self):
  self.docs[0].custom_weekly_status='Pending HR Review';self.docs[0].custom_project_approvals=[]
  self.assertTrue(self.ns['get_hr_weekly_timesheet_queue']()[0]['ready_for_hr_close'])
  self.ns['_team_review_blockers']=lambda d:[{'employee_name':'Member','project':'P','status':'Draft'}]
  self.assertFalse(self.ns['get_hr_weekly_timesheet_queue']()[0]['ready_for_hr_close'])
  with self.assertRaises(ValueError):self.ns['hr_close_weekly_timesheet']('WAIT')
 def test_permissions_and_invalid_views_are_enforced(self):
  with self.assertRaises(ValueError):self.ns['get_hr_weekly_timesheet_queue']('invalid')
  self.ns['_require_hr']=lambda:(_ for _ in ()).throw(PermissionError())
  with self.assertRaises(PermissionError):self.ns['get_hr_weekly_timesheet_queue']()
if __name__=='__main__': unittest.main()
