"""The home card counts the same submitted weeks as the Desk queue."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
class TestCounts(unittest.TestCase):
 def test_total_and_ready_are_distinct_and_permission_scoped(self):
  path=Path(__file__).parents[1]/'api'/'admin_desk.py'
  node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='get_admin_desk_counts')
  node.decorator_list=[];node.body=[n for n in node.body if not isinstance(n,ast.ImportFrom)]
  allowed=True;views=[]
  def queue(view):views.append(view);return [{'ready_for_hr_close':i<3} for i in range(15)]
  ns={'frappe':SimpleNamespace(has_permission=lambda *a:allowed),'_admin_desk_sections':lambda:[{'items':[{'count_key':'hr-timesheets'}]}],'get_hr_weekly_timesheet_queue':queue}
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
  self.assertEqual(ns['get_admin_desk_counts'](),{'hr-timesheets':15,'hr-timesheets-ready':3});self.assertEqual(views,['current'])
  allowed=False;views.clear();self.assertEqual(ns['get_admin_desk_counts'](),{'hr-timesheets':None});self.assertEqual(views,[])
  allowed=True;ns['get_hr_weekly_timesheet_queue']=lambda view:[{'ready_for_hr_close':i<12} for i in range(500)]
  self.assertEqual(ns['get_admin_desk_counts'](),{'hr-timesheets':500,'hr-timesheets-ready':12,'hr-timesheets-capped':True})
if __name__=='__main__':unittest.main()
