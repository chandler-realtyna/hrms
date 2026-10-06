"""No fallback work hours; approved yearly schedule and absence adjustments."""
import ast,sys,types,unittest
from pathlib import Path
from datetime import date,time,timedelta
from types import SimpleNamespace as N
class TestExpected(unittest.TestCase):
 def setUp(self):
  self.schedule=N(timezone='Asia/Yerevan',schedule_days=[N(day_of_week=i,day_type='Working' if i<5 else 'Off',start_time='09:00',end_time='17:00') for i in range(7)])
  self.missing=False;self.leaves=[];self.holiday=False
  calendar=types.ModuleType('hrms.api.calendar');calendar._parse_hhmm=lambda s:time.fromisoformat(s);calendar._is_personal_holiday=lambda e,d:self.holiday and d.weekday()==0
  sys.modules['hrms.api.calendar']=calendar
  def value(dt,key,field):
   if dt=='Employee Schedule':return None if self.missing else 'S'
   return None
  f=N(db=N(get_value=value,exists=lambda *a:False),get_doc=lambda *a:self.schedule,get_all=lambda *a,**k:self.leaves)
  self.env={'frappe':f,'getdate':lambda d:date.fromisoformat(d) if isinstance(d,str) else d,'add_days':lambda d,n:d+timedelta(days=n),'cint':lambda n:int(n or 0),'get_system_timezone':lambda:'EST','_':lambda s:s}
  path=Path(__file__).parents[1]/'api'/'weekly_timesheet.py';nodes=[n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_expected_week_hours'];exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),self.env)
 def calc(self):return self.env['_expected_week_hours']('E','2026-10-04','2026-10-10')
 def test_missing_is_unknown_not_forty(self):self.missing=True;self.assertIsNone(self.calc()['hours'])
 def test_schedule_and_personal_holiday(self):self.assertEqual(self.calc()['hours'],40);self.holiday=True;self.assertEqual(self.calc()['hours'],32)
 def test_half_day_and_overnight_unknown(self):
  self.leaves=[N(half_day=1,half_day_date='2026-10-05')];self.assertEqual(self.calc()['hours'],4)
  self.schedule.schedule_days[0].end_time='08:00';self.assertIsNone(self.calc()['hours'])
if __name__=='__main__':unittest.main()
