"""Execute the actual scoped queue SQL on an isolated relational fixture."""
import ast, base64, hashlib, json, re, sqlite3, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import date

class Row(dict):
 def __getattr__(self, key): return self.get(key)
 def __setattr__(self, key, value): self[key]=value

class TestTeamLifecycle(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  self.db.executescript('''
   CREATE TABLE tabEmployee(name TEXT,status TEXT,user_id TEXT,docstatus INT);
   CREATE TABLE tabUser(name TEXT,enabled INT);
   CREATE TABLE tabProject(name TEXT,project_name TEXT,custom_project_lead TEXT,custom_project_manager TEXT);
   CREATE TABLE tabTimesheet(name TEXT,employee TEXT,employee_name TEXT,custom_is_weekly INT,docstatus INT,custom_weekly_status TEXT,custom_week_start TEXT,custom_week_end TEXT,modified TEXT,custom_weekly_submitted_at TEXT,company TEXT);
   CREATE TABLE "tabTimesheet Detail"(name TEXT,parent TEXT,parenttype TEXT,project TEXT,from_time TEXT,hours REAL,activity_type TEXT);
   CREATE TABLE "tabTimesheet Project Approval"(name TEXT,parent TEXT,project TEXT,status TEXT,return_reason TEXT,reviewed_by TEXT,reviewed_at TEXT);
   INSERT INTO tabEmployee VALUES('worker','Active','worker-user',0);
   INSERT INTO tabUser VALUES('worker-user',1);
   INSERT INTO tabProject VALUES('P','Project','lead',NULL);
  ''')
  for name,status in [('pending','Pending'),('approved','Approved'),('returned','Returned')]:
   self.db.execute('INSERT INTO tabTimesheet VALUES(?,?,?,?,?,?,?,?,?,?,?)',(name,'worker','Worker',1,0,'Pending Project Approval','2026-09-27','2026-10-03','2026-10-01 10:00:00','2026-10-01 09:00:00','Company A'))
   self.db.execute('INSERT INTO "tabTimesheet Detail" VALUES(?,?,?,?,?,?,?)',(name+'-log',name,'Timesheet','P','2026-09-28 09:00:00',1,'Support'))
   self.db.execute('INSERT INTO "tabTimesheet Project Approval" VALUES(?,?,?,?,?,?,?)',(name+'-approval',name,'P',status,None,None,None))
  def sql(query,args,as_dict=False):
   rows=self.db.execute(re.sub(r'%\((\w+)\)s',r':\1',query),args)
   return [Row(zip([c[0] for c in rows.description],values)) if as_dict else values for values in rows.fetchall()]
  def throw(message,*args): raise ValueError(message)
  frappe=NS(ValidationError=ValueError,session=NS(user='Admin'),parse_json=lambda v:json.loads(v) if isinstance(v,str) else v,throw=throw,db=NS(sql=sql,get_value=lambda *a:None,get_all=lambda *a,**k:['Support']))
  self.env=dict(frappe=frappe,_=lambda s:s,_is_hr=lambda:True,_hr_employee_image=lambda employee:None,getdate=lambda v:date.fromisoformat(v),base64=base64,hashlib=hashlib,json=json)
  path=Path(__file__).parents[1]/'api'/'team_timesheets.py'
  nodes=[n for n in ast.parse(path.read_text()).body if not isinstance(n,(ast.Import,ast.ImportFrom))]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),self.env)
 def tearDown(self):self.db.close()
 def page(self,view='current'):return self.env['get_sections'](view)
 def test_completed_project_review_moves_to_history_before_week_is_closed(self):
  current=self.page();history=self.page('history')
  self.assertEqual(current['total'],2);self.assertEqual({r.timesheet for r in current['rows']},{'pending','returned'})
  self.assertEqual(history['total'],1);self.assertEqual(history['rows'][0].timesheet,'approved')
  self.assertFalse(history['rows'][0].actionable)
  self.assertIn('Final weekly approval',history['rows'][0].selection_reason)
 def test_changed_approved_entry_reappears_when_review_is_invalidated(self):
  self.db.execute('UPDATE "tabTimesheet Project Approval" SET status="Pending" WHERE parent="approved"')
  self.assertEqual(self.page()['total'],3);self.assertEqual(self.page('history')['total'],0)
 def test_inactive_disabled_and_missing_accounts_leave_current_without_erasing_records(self):
  mutations=['UPDATE tabEmployee SET status="Left"','UPDATE tabEmployee SET status="Active"; UPDATE tabUser SET enabled=0','DELETE FROM tabUser','DELETE FROM tabEmployee']
  for mutation in mutations:
   with self.subTest(mutation=mutation):
    self.db.executescript(mutation)
    self.assertEqual(self.page()['total'],0)
    history=self.page('history');self.assertEqual(history['total'],3)
    self.assertTrue(all(r.inactive_employee and not r.actionable for r in history['rows']))
    self.assertTrue(all('inactive' in r.selection_reason for r in history['rows']))
    self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tabTimesheet').fetchone()[0],3)
if __name__=='__main__':unittest.main()
