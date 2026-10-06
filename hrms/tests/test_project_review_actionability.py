import ast,unittest
from pathlib import Path
from types import SimpleNamespace as NS
p=Path(__file__).parents[1]/'api'/'weekly_timesheet.py'
nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'_project_section_actionable','_project_section_review_hint'}]
ns={'PENDING_PROJECT':'Pending Project Approval','CORRECTION_REQUIRED':'Correction Required','WEEKLY_DRAFT':'Draft','CLOSED':'Closed','APPROVAL_PENDING':'Pending','APPROVAL_RETURNED':'Returned','APPROVAL_APPROVED':'Approved','APPROVAL_HR':'HR Review','_':lambda s:s}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns)
class TestActionability(unittest.TestCase):
 def test_pending_sibling_remains_reviewable_during_another_projects_correction(self):
  doc=NS(docstatus=0,custom_weekly_submitted_at='2026-10-06',custom_weekly_status='Correction Required')
  self.assertTrue(ns['_project_section_actionable'](doc,NS(status='Pending')))
  self.assertFalse(ns['_project_section_actionable'](doc,NS(status='Returned')))
 def test_drafts_finalized_and_hr_routed_sections_do_not_offer_project_approval(self):
  for stage,submitted,status,docstatus in [('Draft',None,'Pending',0),('Pending Project Approval',None,'Pending',0),('Closed','saved','Approved',1),('Pending HR Review','saved','HR Review',0)]:
   with self.subTest(stage=stage):
    doc=NS(docstatus=docstatus,custom_weekly_submitted_at=submitted,custom_weekly_status=stage)
    self.assertFalse(ns['_project_section_actionable'](doc,NS(status=status)))
 def test_draft_and_returned_hints_explain_employee_action(self):
  doc=NS(docstatus=0,custom_weekly_submitted_at=None,custom_weekly_status='Draft')
  self.assertIn('submit',ns['_project_section_review_hint'](doc,None))
  doc.custom_weekly_submitted_at='saved';doc.custom_weekly_status='Correction Required'
  self.assertIn('resubmit',ns['_project_section_review_hint'](doc,NS(status='Returned')))
if __name__=='__main__':unittest.main()
