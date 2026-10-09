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
  self.env=dict(check_hr_review_permission=lambda *a,**k:None,hashlib=hashlib,json=json,frappe=NS(parse_json=json.loads,session=NS(user='lead'),db=NS(sql=lambda *a:None),get_doc=lambda *a:self.doc,throw=throw,PermissionError=ValueError), _=lambda s:s,flt=lambda x:float(x or 0),cint=lambda x:int(x or 0),get_datetime=datetime.fromisoformat,now_datetime=lambda:datetime(2026,10,6),_project_lead_user=lambda p:'lead',_project_lead_employee=lambda p:'lead-employee',_project_manager_user=lambda p:'manager',_employee_user=lambda e:'worker',_is_hr=lambda:False,_employee_has_active_account=lambda e:True,_team_review_blockers=lambda d:[],_refresh_ready_lead_weeks=lambda *a:None,_notify=lambda *a:None,_hr_users=lambda:[],_serialize_weekly=lambda d:d,_mark_correction=lambda d,*a:setattr(d,'custom_weekly_status','Correction Required'),WEEKLY_DRAFT='Draft',PENDING_PROJECT='Pending Project Approval',CORRECTION_REQUIRED='Correction Required',PENDING_HR='Pending HR Review',CLOSED='Closed',APPROVAL_PENDING='Pending',APPROVAL_APPROVED='Approved',APPROVAL_RETURNED='Returned',APPROVAL_HR='HR Review')
  names={'_entry_revision','_entry_reviews','_project_hours_map','_refresh_approval_hours','_set_project_approvals','_project_reviews_ready','_refresh_review_routing','review_saved_project_entries','reopen_weekly_timesheet','_assert_employee_owns','submit_weekly_timesheet','reset_project_review','return_timesheet_entries','hr_return_weekly_timesheet'}
  nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
  for n in nodes:n.decorator_list=[]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)
 def test_project_total_refresh_preserves_review_evidence(self):
  self.approve()
  approval=self.doc.custom_project_approvals[0]
  self.assertEqual(approval.total_hours,2)
  evidence=approval.entry_reviews
  self.doc.time_logs[0].hours=1.5
  self.env['_refresh_approval_hours'](self.doc)
  self.assertEqual(approval.total_hours,2.5)
  self.assertEqual(approval.entry_reviews,evidence)
  self.assertEqual(approval.status,'Approved')
 def prepare_hr_return(self):
  nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'_mark_correction','_correction_scope'}]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)
  self.env['frappe'].as_json=json.dumps
  self.doc.custom_weekly_status='Pending Project Approval'
  self.doc.custom_weekly_submitted_at='submitted'
  self.env['_project_lead_user']=lambda p:'worker'
  self.env['_project_lead_employee']=lambda p:'worker'
  self.env['_require_hr']=lambda:None
  self.env['_is_hr']=lambda:True
  self.env['frappe'].session.user='hr'
 def test_hr_selected_return_uses_same_routing_as_display(self):
  self.prepare_hr_return()
  times=copy.deepcopy(self.doc.time_logs)
  result=self.env['return_timesheet_entries']('week',['one'],'Check this entry',stage='hr')
  self.assertEqual(result,{'status':'Correction Required','returned':1})
  self.assertEqual([{k:v for k,v in row.items() if k!='custom_return_reason'} for row in self.doc.time_logs],times)
  self.assertEqual(self.doc.time_logs[0].custom_return_reason,'Check this entry')
  self.assertIsNone(self.doc.time_logs[1].custom_return_reason)
  self.assertEqual(json.loads(self.doc.custom_correction_scope)['entries'],['one'])
  self.assertTrue(self.doc.saved)
 def test_hr_whole_week_return_uses_same_routing_as_display(self):
  self.prepare_hr_return()
  times=copy.deepcopy(self.doc.time_logs)
  result=self.env['hr_return_weekly_timesheet']('week','Check the week')
  self.assertEqual(result.custom_weekly_status,'Correction Required')
  self.assertEqual([{k:v for k,v in row.items() if k!='custom_return_reason'} for row in self.doc.time_logs],times)
  self.assertEqual(json.loads(self.doc.custom_correction_scope)['entries'],['one','two'])
 def test_hr_returns_reject_incomplete_project_review(self):
  self.prepare_hr_return()
  self.env['_project_lead_user']=lambda p:'other-lead'
  self.env['_project_lead_employee']=lambda p:'other-worker'
  for action in (lambda:self.env['return_timesheet_entries']('week',['one'],'Check',stage='hr'),lambda:self.env['hr_return_weekly_timesheet']('week','Check')):
   with self.assertRaisesRegex(ValueError,'not ready'):action()
  self.assertFalse(self.doc.saved)
 def test_whole_week_return_rejects_unsubmitted_and_finalized(self):
  self.prepare_hr_return()
  self.doc.custom_weekly_submitted_at=None
  self.doc.custom_weekly_status='Pending HR Review'
  with self.assertRaisesRegex(ValueError,'not ready'):self.env['hr_return_weekly_timesheet']('week','Check')
  self.doc.custom_weekly_submitted_at='submitted';self.doc.docstatus=1
  with self.assertRaisesRegex(ValueError,'not ready'):self.env['hr_return_weekly_timesheet']('week','Check')
 def test_hr_return_locks_before_read(self):
  self.prepare_hr_return()
  events=[]
  self.env['frappe'].db.sql=lambda *a:events.append('lock')
  self.env['frappe'].get_doc=lambda *a:(events.append('read') or self.doc)
  self.env['return_timesheet_entries']('week',['one'],'Check',stage='hr')
  self.assertEqual(events[:2],['lock','read'])
 def test_hr_exception_requires_reason(self):
  self.env['_is_hr']=lambda:True
  self.env['frappe'].session.user='hr'
  with self.assertRaisesRegex(ValueError,'requires a reason'): self.approve()
  self.env['review_saved_project_entries']('week','P','v1',reason='Lead unavailable')
  self.assertTrue(self.doc.saved)
 def test_hr_reset_preserves_other_sections_and_entries(self):
  self.doc.time_logs.append(self.log('other','Q'))
  self.approve();self.env['review_saved_project_entries']('week','Q','v1')
  self.doc.custom_weekly_submitted_at='submitted';self.doc.custom_weekly_status='Pending HR Review'
  self.env['_require_hr']=lambda:None
  self.env['_notify_project_report']=lambda *a:None
  self.env['frappe'].session.user='hr'
  self.env['reset_project_review']('week','P','v1','Lead must recheck')
  states={a.project:a.status for a in self.doc.custom_project_approvals}
  self.assertEqual(states,{'P':'Pending','Q':'Approved'})
  self.assertEqual(len(self.doc.time_logs),3)
  self.assertEqual(self.doc.custom_weekly_status,'Pending Project Approval')
  self.doc.docstatus=1
  with self.assertRaisesRegex(ValueError,'Finalized'):self.env['reset_project_review']('week','Q','v1','Recheck')
 def log(self,name,project='P'):
  return Record(name=name,project=project,activity_type='Support',description='work',from_time='2026-10-05 09:00:00',to_time='2026-10-05 10:00:00',hours=1,is_billable=1)
 def approve(self,entries=None):return self.env['review_saved_project_entries']('week','P','v1',entries=entries)
 def test_approve_draft_keeps_employee_submission_separate(self):
  self.approve();self.assertEqual(self.doc.custom_weekly_status,'Draft');self.assertIsNone(self.doc.custom_weekly_submitted_at)
  self.assertTrue(self.env['_project_reviews_ready'](self.doc))
 def test_personal_submission_does_not_wait_for_other_employees(self):
  self.env['ALLOWED_EMPLOYEE_STATES']={'Draft','Correction Required'}
  self.env['_employee_user']=lambda e:'lead'
  self.env['_project_lead_employee']=lambda p:'worker'
  self.env['_team_review_blockers']=lambda d:(_ for _ in ()).throw(AssertionError('Unrelated team work queried'))
  self.env['submit_weekly_timesheet']('week')
  self.assertEqual(self.doc.custom_weekly_status,'Pending HR Review')
  self.assertIsNotNone(self.doc.custom_weekly_submitted_at)
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
  self.env['_team_review_blockers']=lambda d:(_ for _ in ()).throw(AssertionError('Team work blocked own routing'))
  self.env['_refresh_review_routing'](self.doc)
  self.assertEqual(self.doc.custom_project_approvals[0].status,'HR Review')
  self.assertEqual(self.doc.custom_weekly_status,'Pending HR Review')
  self.assertFalse(self.doc.saved)
 def test_completed_team_review_does_not_wait_for_team_submission(self):
  self.approve()
  nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_pending_team_reviews']
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)
  self.env['frappe'].get_all=lambda dt,**kw:['P'] if dt=='Project' else [NS(name='week',employee_name='Worker')]
  lead_week=Record(employee='lead-employee',custom_week_start='2026-10-04')
  self.assertEqual(self.env['_pending_team_reviews'](lead_week),[])
  self.doc.time_logs[0].description='changed since approval'
  self.assertEqual(len(self.env['_pending_team_reviews'](lead_week)),1)
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
  self.env['_project_lead_employee']=lambda p:'worker'
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
