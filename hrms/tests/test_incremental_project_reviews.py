"""Saved-entry approvals: revisions, legacy evidence, scope and weekly gates."""
import ast, copy, hashlib, json, unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
SOURCE = Path(__file__).parents[1] / 'api' / 'weekly_timesheet.py'
class Record(dict):
 def __getattr__(self, key): return self.get(key)
 def __setattr__(self, key, value): self[key] = value
 def is_new(self): return False
 def get_doc_before_save(self): return self.get('_old')
 def append(self, field, values):
  row=Record(values); self[field].append(row); return row
 def remove(self, row): self.custom_project_approvals.remove(row)
 def save(self, **kwargs): self.saved=True
 def add_comment(self, *args): self.comment=args
class TestIncrementalReviews(unittest.TestCase):
 def setUp(self):
  def throw(message,*args): raise ValueError(message)
  self.doc=Record(name='week',employee='worker',employee_name='Worker',docstatus=0,custom_is_weekly=1,custom_weekly_status='Draft',custom_weekly_submitted_at=None,custom_week_start='2026-10-04',modified='v1',time_logs=[self.log('one'),self.log('two')],custom_project_approvals=[],flags=Record())
  self.env=dict(hashlib=hashlib,json=json,frappe=NS(parse_json=json.loads,session=NS(user='lead'),db=NS(sql=lambda *a:None),get_doc=lambda *a:self.doc,throw=throw,PermissionError=ValueError), _=lambda s:s,flt=lambda x:float(x or 0),cint=lambda x:int(x or 0),get_datetime=datetime.fromisoformat,now_datetime=lambda:datetime(2026,10,6),_project_lead_user=lambda p:'lead',_project_lead_employee=lambda p:'lead-employee',_project_manager_user=lambda p:'manager',_employee_user=lambda e:'worker',_is_hr=lambda:False,_team_review_blockers=lambda d:[],_refresh_ready_lead_weeks=lambda *a:None,_notify=lambda *a:None,_hr_users=lambda:[],_serialize_weekly=lambda d:d,_mark_correction=lambda d,*a:setattr(d,'custom_weekly_status','Correction Required'),WEEKLY_DRAFT='Draft',PENDING_PROJECT='Pending Project Approval',CORRECTION_REQUIRED='Correction Required',PENDING_HR='Pending HR Review',CLOSED='Closed',APPROVAL_PENDING='Pending',APPROVAL_APPROVED='Approved',APPROVAL_RETURNED='Returned',APPROVAL_HR='HR Review')
  names={'_entry_revision','_entry_reviews','_set_project_approvals','_project_reviews_ready','_refresh_review_routing','review_saved_project_entries','reopen_weekly_timesheet','_assert_employee_owns'}
  nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
  for n in nodes:n.decorator_list=[]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)
 def log(self,name,project='P'):
  return Record(name=name,project=project,activity_type='Support',description='work',from_time='2026-10-05 09:00:00',to_time='2026-10-05 10:00:00',hours=1,is_billable=1)
 def approve(self,entries=None):return self.env['review_saved_project_entries']('week','P','v1',entries=entries)
 def test_approve_draft_keeps_employee_submission_separate(self):
  self.approve();self.assertEqual(self.doc.custom_weekly_status,'Draft');self.assertIsNone(self.doc.custom_weekly_submitted_at)
  self.assertTrue(self.env['_project_reviews_ready'](self.doc))
 def test_partial_approval_only_covers_selected_entry(self):
  self.approve(['one']);self.assertEqual(self.doc.custom_project_approvals[0].status,'Pending')
  self.assertEqual(set(json.loads(self.doc.custom_project_approvals[0].entry_reviews)),{'one'})
 def test_edit_invalidates_only_changed_entry(self):
  self.approve();self.doc._old=copy.deepcopy(self.doc);self.doc.time_logs[0].description='changed'
  self.env['_set_project_approvals'](self.doc)
  self.assertEqual(set(json.loads(self.doc.custom_project_approvals[0].entry_reviews)),{'two'})
  self.assertFalse(self.env['_project_reviews_ready'](self.doc))
 def test_delete_and_project_move_remove_old_review(self):
  self.approve();self.doc._old=copy.deepcopy(self.doc);self.doc.time_logs.pop(0)
  self.env['_set_project_approvals'](self.doc);self.assertTrue(self.env['_project_reviews_ready'](self.doc))
  self.doc.time_logs[0].project='Q';self.env['_set_project_approvals'](self.doc)
  self.assertEqual([a.project for a in self.doc.custom_project_approvals],['Q'])
  self.assertFalse(self.env['_project_reviews_ready'](self.doc))
 def test_legacy_approval_seeds_before_image_not_changed_values(self):
  self.doc.custom_project_approvals=[Record(project='P',status='Approved',controller='lead',reviewed_by='lead',reviewed_at='yesterday')]
  self.doc._old=copy.deepcopy(self.doc);self.doc.time_logs[0].hours=2
  self.env['_set_project_approvals'](self.doc)
  self.assertEqual(set(json.loads(self.doc.custom_project_approvals[0].entry_reviews)),{'two'})
 def test_saved_approvals_survive_submission_and_new_entry_is_pending(self):
  self.approve();self.doc._old=copy.deepcopy(self.doc);self.doc.custom_weekly_status='Pending Project Approval';self.doc.custom_weekly_submitted_at='today'
  self.env['_set_project_approvals'](self.doc);self.assertTrue(self.env['_project_reviews_ready'](self.doc))
  self.doc.time_logs.append(self.log('three'));self.env['_set_project_approvals'](self.doc)
  self.assertEqual(set(json.loads(self.doc.custom_project_approvals[0].entry_reviews)),{'one','two'})
  self.assertFalse(self.env['_project_reviews_ready'](self.doc))
 def test_lead_reassignment_invalidates_previous_review(self):
  self.approve();self.env['_project_lead_user']=lambda p:'new-lead'
  self.env['_set_project_approvals'](self.doc)
  self.assertEqual(self.doc.custom_project_approvals[0].controller,'new-lead')
  self.assertEqual(self.doc.custom_project_approvals[0].status,'Pending')
  self.assertFalse(self.env['_project_reviews_ready'](self.doc))
 def test_self_lead_reassignment_routes_submitted_week_to_hr(self):
  self.doc.custom_weekly_status='Pending Project Approval';self.doc.custom_weekly_submitted_at='submitted'
  self.env['_set_project_approvals'](self.doc)
  self.env['_project_lead_user']=lambda p:'worker';self.env['_project_lead_employee']=lambda p:'worker'
  self.env['_refresh_review_routing'](self.doc)
  self.assertEqual(self.doc.custom_project_approvals[0].status,'HR Review')
  self.assertEqual(self.doc.custom_weekly_status,'Pending HR Review')
  self.assertFalse(self.doc.saved)
 def test_completed_team_review_does_not_wait_for_team_submission(self):
  self.approve()
  nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_team_review_blockers']
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)
  self.env['frappe'].get_all=lambda dt,**kw:['P'] if dt=='Project' else [NS(name='week',employee_name='Worker')]
  lead_week=Record(employee='lead-employee',custom_week_start='2026-10-04')
  self.assertEqual(self.env['_team_review_blockers'](lead_week),[])
  self.doc.time_logs[0].description='changed since approval'
  self.assertEqual(len(self.env['_team_review_blockers'](lead_week)),1)
 def test_owner_withdrawal_preserves_saved_entries_and_approvals(self):
  self.approve();self.doc.custom_weekly_status='Pending HR Review';self.doc.custom_weekly_submitted_at='submitted'
  reviews=self.doc.custom_project_approvals[0].entry_reviews
  self.env['frappe'].session.user='worker'
  result=self.env['reopen_weekly_timesheet']('week','v1','Correct my note')
  self.assertEqual(result.custom_weekly_status,'Draft');self.assertIsNone(result.custom_weekly_submitted_at)
  self.assertEqual(len(result.time_logs),2);self.assertEqual(result.custom_project_approvals[0].entry_reviews,reviews)
  self.assertIn('Correct my note',result.comment[1])
 def test_reopen_permissions_staleness_reason_and_final_lock(self):
  self.doc.custom_weekly_status='Pending Project Approval';self.doc.custom_weekly_submitted_at='submitted'
  with self.assertRaises(ValueError):self.env['reopen_weekly_timesheet']('week','v1','edit')
  self.env['frappe'].session.user='worker'
  with self.assertRaises(ValueError):self.env['reopen_weekly_timesheet']('week','old','edit')
  with self.assertRaises(ValueError):self.env['reopen_weekly_timesheet']('week','v1','')
  self.doc.docstatus=1
  with self.assertRaises(ValueError):self.env['reopen_weekly_timesheet']('week','v1','edit')
  self.doc.docstatus=0;self.env['_is_hr']=lambda:True;self.env['frappe'].session.user='hr'
  self.assertEqual(self.env['reopen_weekly_timesheet']('week','v1','HR requested correction').custom_weekly_status,'Draft')
 def test_permission_self_closed_stale_and_cross_project_rejections(self):
  self.env['_employee_user']=lambda e:'lead'
  with self.assertRaises(ValueError):self.approve()
  self.env['_employee_user']=lambda e:'worker';self.env['frappe'].session.user='outsider'
  with self.assertRaises(ValueError):self.approve()
  self.env['frappe'].session.user='lead';self.doc.docstatus=1
  with self.assertRaises(ValueError):self.approve()
  self.doc.docstatus=0;self.doc.modified='v2'
  with self.assertRaises(ValueError):self.approve()
  self.doc.modified='v1'
  with self.assertRaises(ValueError):self.approve(['other-project'])
 def test_return_revokes_only_selected_approval_and_requires_correction(self):
  self.approve();self.env['review_saved_project_entries']('week','P','v1',entries=['one'],action='return',reason='wrong')
  self.assertEqual(set(json.loads(self.doc.custom_project_approvals[0].entry_reviews)),{'two'})
  self.assertEqual(self.doc.custom_weekly_status,'Draft')
  with self.assertRaises(ValueError):self.approve(['one'])
if __name__=='__main__':unittest.main()
