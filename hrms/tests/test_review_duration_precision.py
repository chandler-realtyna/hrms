"""Keep tracked hour precision until the final duration presentation."""
import ast,unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace as N
class R(dict):
 def __getattr__(self,k):return self.get(k)
class TestPrecision(unittest.TestCase):
 def test_history_preserves_minutes_before_formatting(self):
  path=Path(__file__).parents[1]/'api'/'management_reports.py'
  names={'_aggregate','_status'};nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
  env={'defaultdict':defaultdict,'flt':float};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
  result=env['_aggregate']([R(hours=.042,docstatus=0,custom_weekly_status='Draft',project='P',project_label='Project',employee='E',from_time='2026-10-06')],'project')
  self.assertEqual(result['rows'][0]['hours'],.042)
  self.assertEqual(result['totals']['hours'],.042)
  self.assertEqual(result['totals']['status_hours']['Draft'],.042)
  self.assertEqual(round(result['totals']['hours']*60),3) # .04 prematurely rounded gives 2 min
 def test_project_detail_retains_entry_precision(self):
  path=Path(__file__).parents[1]/'api'/'weekly_timesheet.py'
  node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='get_project_review_detail');node.decorator_list=[]
  row=R(name='entry',project='P',from_time='2026-10-06 09:00:00',to_time='2026-10-06 09:02:31',hours=.042)
  doc=N(name='T',employee='E',employee_name='Person',modified='v',docstatus=0,custom_weekly_status='Draft',custom_week_start='2026-10-04',custom_week_end='2026-10-10',custom_project_approvals=[],time_logs=[row])
  env={'frappe':N(session=N(user='hr'),db=N(get_value=lambda *a:'T'),get_doc=lambda *a:doc),'_is_hr':lambda:True,'getdate':lambda d:d,'_refresh_review_routing':lambda d:None,'get_datetime':__import__('datetime').datetime.fromisoformat,'flt':float,'_project_display_name':lambda p:p,'_entry_reviews':lambda *a:{},'_entry_revision':lambda r:'v','_employee_has_active_account':lambda e:True,'_project_lead_user':lambda p:'lead','_project_manager_user':lambda p:'manager','_employee_user':lambda e:'employee','_project_lead_employee':lambda p:'leader','_project_section_actionable':lambda *a:True,'_project_section_review_hint':lambda *a:'','get_system_timezone':lambda:'UTC','WEEKLY_DRAFT':'Draft','PENDING_PROJECT':'Pending Project Approval','PENDING_HR':'Pending HR Review','CORRECTION_REQUIRED':'Correction Required','CLOSED':'Closed','APPROVAL_APPROVED':'Approved','APPROVAL_HR':'HR Review'}
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
  result=env['get_project_review_detail']('P','2026-10-04','E')
  self.assertEqual(result['logs'][0]['duration'],.042)
if __name__=='__main__':unittest.main()
