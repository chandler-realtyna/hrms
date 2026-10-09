"""Regression tests run without a database; actual invoice calculation functions."""
import ast, copy, hashlib, json, sys, unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS, ModuleType
from unittest.mock import patch
SOURCE=Path(__file__).parents[1]/'api'/'employee_invoice.py'
class Record(dict):
 def __getattr__(self,key): return self.get(key)
 def __setattr__(self,key,value): self[key]=value
 def set(self,key,value): self[key]=value
 def append(self,key,value): self[key].append(value)
class InvoiceHours(unittest.TestCase):
 def setUp(self):
  def throw(message,*a):raise ValueError(message)
  def flt(value,precision=None):
   result=float(value or 0)
   return round(result,precision) if precision is not None else result
  self.env=dict(frappe=NS(throw=throw),_=lambda x:x,flt=flt,cint=lambda x:int(x or 0),getdate=lambda x:x if isinstance(x,date) else date.fromisoformat(x),hashlib=hashlib,json=json,LEAVE_HOURS_PER_DAY=8,INVOICE_LEAVE_TYPES=('Paid Leave','Sick Leave','Unpaid Leave'),ADDITION_TYPES={'Bonus','Commission','Paid Leave Adjustment','Other'},DEDUCTION_TYPES={'Prepayment','Deduction'},apply_invoice_terms=lambda d:None)
  names={'_effective_total_hours','_calculate_amounts','_hash','_material_payload','_recalculate','_leave_totals','_leave_summary','_paid_holiday_rows','_leave_rows'}
  nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names]
  for n in nodes:n.decorator_list=[]
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)
 def test_169_worked_plus_one_paid_holiday(self):
  result=self.env['_calculate_amounts']('Hourly',169,0,10,[],due_hours=177,paid_holiday_hours=8)
  self.assertEqual(result,(1770,0,0,1770,177,0))
 def test_due_hours_cannot_change_hourly_worked_total(self):
  for due in (0,177,500):
   self.assertEqual(self.env['_calculate_amounts']('Hourly',169,0,10,[],due_hours=due)[4],169)
 def test_proposal_replaces_total_without_double_adding_holidays(self):
  self.assertEqual(self.env['_calculate_amounts']('Hourly',136,0,10,[],paid_holiday_hours=8,total_hours_override=177)[4],177)
  self.assertEqual(self.env['_calculate_amounts']('Hourly',136,0,10,[],total_hours_override=0)[3],0)
 def test_proposal_requires_reason_and_finite_nonnegative_number(self):
  doc=Record(worked_hours=169,paid_holiday_hours=8,use_hours_override=1)
  for value in (-1,'bad',float('nan'),float('inf'),None):
   doc.employee_total_hours=value
   with self.assertRaises(ValueError):self.env['_effective_total_hours'](doc)
  doc.employee_total_hours=177
  with self.assertRaises(ValueError):self.env['_effective_total_hours'](doc)
  doc.hours_override_reason='Approved correction'
  self.assertEqual(self.env['_effective_total_hours'](doc),177)
 def test_fixed_monthly_money_unchanged_by_holiday_or_proposal(self):
  result=self.env['_calculate_amounts']('Fixed Monthly',169,1000,0,[],due_hours=160,unpaid_leave_hours=8,paid_holiday_hours=8,total_hours_override=177)
  self.assertEqual((result[3],result[4]),(950,177))
 def test_recalculation_keeps_worked_hours_separate_and_period_scoped(self):
  doc=Record(employee='E',period_start='2026-09-01',period_end='2026-09-30',calculation_method='Hourly',hourly_rate=10,monthly_amount=0,adjustments=[],due_hours=177,use_hours_override=1,employee_total_hours=177,hours_override_reason='Correction')
  self.env['_timesheet_rows']=lambda e,a,b:([dict(timesheet='T',work_date=a,hours=136.49,approval_status='Finalized')],True)
  self.env['_paid_holiday_rows']=lambda *a:[dict(date='2026-09-21',description='Holiday',hours=8)]
  self.env['_leave_rows']=lambda *a:[]
  self.env['_recalculate'](doc)
  self.assertEqual((doc.worked_hours,doc.paid_holiday_hours,doc.system_total_hours,doc.payable_hours),(136.49,8,144.49,177))
  self.assertEqual(doc.time_summary[0]['hours'],136.49)
 def test_confirmation_hash_covers_proposal_reason_and_holiday_source(self):
  doc=Record(period_start='2026-09-01',period_end='2026-09-30',adjustments=[],worked_hours=169,paid_holiday_hours=8,system_total_hours=177,employee_total_hours=177,use_hours_override=1,hours_override_reason='Correction')
  original=self.env['_hash'](self.env['_material_payload'](doc))
  doc.hours_override_reason='Different reason'
  self.assertNotEqual(original,self.env['_hash'](self.env['_material_payload'](doc)))
  doc.hours_override_reason='Correction';doc.holiday_source_hash='changed holiday dates'
  self.assertNotEqual(original,self.env['_hash'](self.env['_material_payload'](doc)))
 def test_holidays_deduplicate_personal_and_public_and_follow_assignment(self):
  mod=ModuleType('erpnext.setup.doctype.employee.employee')
  mod.get_holiday_list_for_employee=lambda employee,**kw:'A' if str(kw['as_on'])=='2026-09-21' else 'B'
  def get_all(dt,filters=None,**kw):
   if dt=='Employee Holiday':return ['personal']
   if dt=='Employee Holiday Date':return [Record(date='2026-09-21',description='Personal')]
   self.assertEqual(filters['weekly_off'],0)
   return [Record(holiday_date='2026-09-21',description='Public')] if filters['parent']=='A' else []
  self.env['frappe'].get_all=get_all
  with patch.dict(sys.modules,{'erpnext.setup.doctype.employee.employee':mod}):
   rows=self.env['_paid_holiday_rows']('E','2026-09-21','2026-09-22')
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['hours'],8)
 def test_holiday_not_also_credited_or_deducted_as_leave(self):
  mod=ModuleType('hrms.hr.doctype.leave_application.leave_application')
  mod.get_number_of_leave_days=lambda *a,**kw:(self.env['getdate'](a[3])-self.env['getdate'](a[2])).days+1
  self.env['frappe'].get_all=lambda *a,**kw:[Record(name='L',leave_type='Paid Leave',from_date='2026-09-21',to_date='2026-09-22',modified='v1')]
  with patch.dict(sys.modules,{'hrms.hr.doctype.leave_application.leave_application':mod}):
   rows=self.env['_leave_rows']('E','2026-09-01','2026-09-30',{'2026-09-21'})
  self.assertEqual(rows[0]['hours'],8)
if __name__=='__main__':unittest.main()
