import ast,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from collections import defaultdict
from datetime import date,timedelta
class R(dict):
 def __getattr__(self,k):return self.get(k)
def get_all(dt,**kw):
 if dt=='Project':return [R(name='P',project_name='HR system',company='A'),R(name='Q',project_name='Empty project',company='B')]
 return [R(parent='TS',project='P',status='HR Review')]
source=Path(__file__).parents[1] / 'api' / 'management_reports.py'
nodes=[n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='get_daily_project_summary']
# strip local framework import; supplies bounds fake
for n in nodes:n.decorator_list=[];n.body=[b for b in n.body if not isinstance(b,ast.ImportFrom)]
e=dict(frappe=NS(get_all=get_all),defaultdict=defaultdict,flt=float,add_days=lambda d,x:d+timedelta(days=x),_week_bounds=lambda d:(date(2026,10,4),date(2026,10,10)),_project_scope=lambda:None,_read_entries=lambda *a:[R(project='P',employee='Lucas',employee_name='Lucas',timesheet='TS',from_time='2026-10-06 09:00:00',hours=1.7,activity_type=None)])
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),e)
r=e['get_daily_project_summary']();assert len(r)==2;assert r[0]['members'][0]['weekly_total']==1.7;assert r[0]['members'][0]['status']=='HR Review';assert r[1]['members']==[]
print('SUMMARY_COVERAGE_OK: HR-routed entries and empty projects retained')
