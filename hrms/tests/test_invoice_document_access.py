"""Known invoice identifiers cannot bypass native HR user permissions."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

class TestInvoiceDocumentAccess(unittest.TestCase):
 def load(self, owner='employee', status='Pending HR Review', hr=True, company=True, native=True):
  calls=[]
  def check(permission):
   calls.append(permission)
   if not native:raise PermissionError('Employee restricted')
  doc=NS(employee_user=owner,status=status,company='Company',check_permission=check)
  def throw(message,*args):raise PermissionError(message)
  env={'frappe':NS(session=NS(user='viewer'),get_doc=lambda *a:doc,throw=throw,PermissionError=PermissionError),'_':lambda x:x,'_is_hr':lambda:hr,'_can_access_company':lambda *a:company}
  path=Path(__file__).parents[1]/'api/employee_invoice.py'
  node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='_get_doc')
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
  return env['_get_doc'],doc,calls
 def test_native_employee_permission_denial_stops_hr(self):
  get,doc,calls=self.load(native=False)
  with self.assertRaisesRegex(PermissionError,'Employee restricted'):get('INV')
  self.assertEqual(calls,['read'])
 def test_allowed_hr_checks_native_read_only(self):
  get,doc,calls=self.load()
  self.assertIs(get('INV'),doc);self.assertEqual(calls,['read'])
 def test_own_invoice_remains_accessible_including_draft(self):
  for status in ['Draft','Pending HR Review','Paid']:
   get,doc,calls=self.load(owner='viewer',status=status,hr=False,company=False,native=False)
   self.assertIs(get('INV'),doc);self.assertEqual(calls,[])
 def test_other_employee_draft_remains_private(self):
  get,doc,calls=self.load(status='Draft')
  with self.assertRaisesRegex(PermissionError,'drafts are private'):get('INV')
  self.assertEqual(calls,[])
 def test_company_denial_and_nonhr_denial_preserved(self):
  for hr,company in [(True,False),(False,True)]:
   get,doc,calls=self.load(hr=hr,company=company)
   with self.assertRaises(PermissionError):get('INV')
   self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
