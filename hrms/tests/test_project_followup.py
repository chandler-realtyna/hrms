"""Explicit reminder guards and duplicate protection, with no real notifications."""
import ast,unittest
from pathlib import Path
from types import SimpleNamespace as N
from datetime import datetime,timedelta
class Doc(N):
 def check_permission(self,p):
  if not self.allowed:raise ValueError('denied read')
 def add_comment(self,*a):self.comments.append(a)
class TestFollowup(unittest.TestCase):
 def setUp(self):
  self.sent=[];self.last=None;self.hr=True;self.active=True;self.enabled=True
  self.doc=Doc(employee='worker',employee_name='Worker',allowed=True,modified='v1',docstatus=0,custom_is_weekly=1,custom_weekly_status='Pending Project Approval',custom_weekly_submitted_at='2026-10-01',custom_week_start='2026-09-27',custom_week_end='2026-10-03',custom_project_approvals=[N(project='P',status='Pending')],time_logs=[N(project='P')],comments=[])
  def throw(msg,*a):raise ValueError(msg)
  def require():
   if not self.hr:throw('HR required')
  def value(dt,key,field,**kw):
   if dt=='Notification Log':return self.last
   if dt=='Project' and field=='project_name':return 'HR System'
   if dt=='User':return self.enabled if field=='enabled' else 'Lead Person'
   if dt=='Employee':return 'leader' if self.active else None
  def getdoc(dt,*args):
   if isinstance(dt,dict):return N(insert=lambda **kw:self.sent.append(dt))
   return self.doc
  self.env={'escape':__import__('html').escape,'frappe':N(session=N(user='hr'),throw=throw,db=N(sql=lambda *a:None,get_value=value),get_doc=getdoc,bold=lambda s:s,PermissionError=ValueError),'_':lambda s:s,'_require_hr':require,'_employee_user':lambda e:'worker','_employee_has_active_account':lambda e:self.active,'_project_lead_user':lambda p:'lead','_project_manager_user':lambda p:'manager','_project_lead_employee':lambda p:'leader','PENDING_PROJECT':'Pending Project Approval','APPROVAL_PENDING':'Pending','get_datetime':datetime.fromisoformat,'now_datetime':lambda:datetime(2026,10,6,12),'add_to_date':lambda dt,hours:dt+timedelta(hours=hours)}
  path=Path(__file__).parents[1]/'api'/'project_review_followup.py';nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)]
  for n in nodes:n.decorator_list=[]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),self.env)
 def ping(self):return self.env['ping_project_reviewer']('T','P','v1',self.env['_project_lead_user']('P'))
 def test_explicit_ping_sends_both_bells_and_audit(self):
  self.assertTrue(self.ping()['sent']);self.assertEqual([n['doctype'] for n in self.sent],['Notification Log','PWA Notification']);self.assertEqual(self.sent[0]['for_user'],'lead');self.assertEqual(len(self.doc.comments),1);self.assertIn('HR System',self.sent[0]['email_content']);self.assertIn('2026-10-03',self.sent[0]['email_content'])
 def test_duplicate_is_noop_with_last_ping(self):
  self.last='2026-10-06 10:00:00';self.assertFalse(self.ping()['sent']);self.assertEqual(self.sent,[]);self.assertEqual(self.doc.comments,[])
 def test_stale_closed_draft_returned_inactive_own_and_membership_are_rejected(self):
  for mutate in [lambda:setattr(self.doc,'modified','new'),lambda:setattr(self.doc,'docstatus',1),lambda:setattr(self.doc,'custom_weekly_status','Draft'),lambda:setattr(self.doc.custom_project_approvals[0],'status','Returned'),lambda:setattr(self,'active',False),lambda:setattr(self.env['frappe'].session,'user','worker'),lambda:setattr(self.doc,'time_logs',[])]:
   self.setUp();mutate()
   with self.assertRaises(ValueError):self.ping()
   self.assertEqual(self.sent,[])
 def test_role_and_document_permission_enforced(self):
  self.hr=False
  with self.assertRaises(ValueError):self.ping()
  self.hr=True;self.doc.allowed=False
  with self.assertRaises(ValueError):self.ping()
 def test_disabled_reviewer_never_receives_reminder(self):
  self.enabled=False
  with self.assertRaisesRegex(ValueError,'active project reviewer'):self.ping()
  self.assertEqual(self.sent,[])
 def test_unavailable_lead_uses_only_active_manager_fallback(self):
  original=self.env['frappe'].db.get_value
  def values(dt,key,field,**kw):
   if dt=='Project':return 'manager-employee'
   if dt=='User' and field=='enabled':return key=='manager-user'
   if dt=='Employee':return 'manager-user' if field=='user_id' else 'manager-employee'
   return original(dt,key,field,**kw)
  self.env['frappe'].db.get_value=values
  result=self.env['ping_project_reviewer']('T','P','v1','manager-user')
  self.assertTrue(result['sent']);self.assertEqual(self.sent[0]['for_user'],'manager-user')
 def test_untrusted_names_are_escaped_in_notification_html(self):
  self.doc.employee_name='<img onerror="bad">'
  self.ping();self.assertNotIn('<img',self.sent[0]['email_content'])
  self.assertEqual(self.env['_reminder_subject']('<project>'),'Project review reminder: &lt;project&gt;')
 def test_usable_lead_does_not_touch_unusable_legacy_manager(self):
  original=self.env['frappe'].db.get_value
  def guarded(dt,*a,**k):
   if dt=='Project' and a[-1]=='custom_project_manager':raise AssertionError('Manager fallback eagerly read')
   return original(dt,*a,**k)
  self.env['frappe'].db.get_value=guarded
  self.assertTrue(self.ping()['sent'])
 def test_assignment_changed_since_browser_is_rejected(self):
  self.env['_project_lead_user']=lambda p:'new-lead'
  with self.assertRaisesRegex(ValueError,'reviewer changed'):self.env['ping_project_reviewer']('T','P','v1','old-lead')
  self.assertEqual(self.sent,[])
 def test_changed_assignment_uses_current_reviewer_not_stored_controller(self):
  self.env['_project_lead_user']=lambda p:'new-lead';self.ping();self.assertEqual(self.sent[0]['for_user'],'new-lead')
if __name__=='__main__':unittest.main()
