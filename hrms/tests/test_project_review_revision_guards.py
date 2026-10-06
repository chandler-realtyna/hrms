"""Client-observed versions and explicit bulk scope, without framework database."""
import ast,unittest
from pathlib import Path
from types import SimpleNamespace as N
class TestRevisionGuards(unittest.TestCase):
 def setUp(self):
  self.docs={'T1':N(name='T1',modified='v1',custom_week_start='2026-10-04',docstatus=0,custom_weekly_status='Draft'),'T2':N(name='T2',modified='v2',custom_week_start='2026-10-04',docstatus=0,custom_weekly_status='Draft')}
  self.rows={'A':N(name='A',parent='T1',project='P'),'B':N(name='B',parent='T2',project='P')};self.calls=[]
  def throw(msg,*a):raise ValueError(msg)
  def getdoc(dt,name):return (self.rows if dt=='Timesheet Project Approval' else self.docs)[name]
  def review(name,project,expected_modified,**kwargs):
   self.assertEqual(self.docs[name].modified,expected_modified);self.calls.append((name,project,kwargs));self.docs[name].modified+='x'
  f=N(parse_json=__import__('json').loads,throw=throw,get_doc=getdoc,db=N(sql=lambda *a:None),get_all=lambda *a,**k:list(self.rows.values()),session=N(user='lead'),PermissionError=ValueError)
  self.env={'frappe':f,'_':lambda s:s,'review_saved_project_entries':review,'_is_hr':lambda:False,'_project_lead_user':lambda p:'lead','_project_manager_user':lambda p:'manager','getdate':lambda s:s,'APPROVAL_PENDING':'Pending'}
  path=Path(__file__).parents[1]/'api'/'weekly_timesheet.py';names={'_review_project_approval_row','_observed_project_sections','_approve_observed_sections','approve_project_reviews','approve_project_week','review_project_approval','approve_project_review'};nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
  for node in nodes:node.decorator_list=[]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),self.env)
 def sections(self):return [{'approval_name':'A','expected_modified':'v1'},{'approval_name':'B','expected_modified':'v2'}]
 def test_stale_member_rejects_before_any_write(self):
  self.docs['T2'].modified='changed'
  with self.assertRaisesRegex(ValueError,'changed'):self.env['approve_project_reviews'](self.sections())
  self.assertEqual(self.calls,[])
 def test_explicit_selection_never_adds_other_members(self):
  result=self.env['approve_project_reviews'](self.sections()[:1]);self.assertEqual(result['approved'],1);self.assertEqual([c[0] for c in self.calls],['T1'])
 def test_legacy_single_approve_is_single_section(self):
  self.env['review_project_approval']('A','approve','v1');self.assertEqual([c[0] for c in self.calls],['T1'])
 def test_week_bulk_rejects_unseen_member(self):
  with self.assertRaisesRegex(ValueError,'sections changed'):self.env['approve_project_week']('P','2026-10-04',self.sections()[:1])
  self.assertEqual(self.calls,[])
 def test_two_sections_same_week_can_be_approved_after_prevalidation(self):
  self.rows['B'].parent='T1';parts=self.sections();parts[1]['expected_modified']='v1'
  self.assertEqual(self.env['approve_project_reviews'](parts)['approved'],2)
 def test_missing_and_duplicate_observed_revisions_rejected(self):
  for sections in [None,[{'approval_name':'A'}],self.sections()[:1]*2]:
   with self.assertRaises(ValueError):self.env['approve_project_reviews'](sections)
if __name__=='__main__':unittest.main()
