"""Synthetic document events and transactional email queues; no external delivery."""
import unittest
import json
from email import policy
from email.parser import Parser
from unittest.mock import MagicMock, patch

import frappe

from hrms.tests import test_shared_work_state as fixtures
from hrms.utils import review_notifications as mail


class TestReviewEmails(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		assert frappe.local.site == "qa.local", "Email acceptance is restricted to the synthetic site"
		fixtures.TestSharedWorkState.setUpClass.__func__(cls)

	def setUp(self):
		fixtures.TestSharedWorkState.setUp(self)
		frappe.set_user("Administrator")
		for doctype in mail.REVIEW_TYPES:
			names = frappe.get_all(doctype, filters={"employee": self.employees[0]}, pluck="name")
			for field in frappe.get_meta(doctype).get_table_fields():
				if names: frappe.db.delete(field.options, {"parent": ("in", names), "parenttype": doctype})
			frappe.db.delete(doctype, {"employee": self.employees[0]})

	tearDown = fixtures.TestSharedWorkState.tearDown

	def invoice(self):
		doc = frappe.get_doc(dict(doctype="Employee Invoice", employee=self.employees[0],
			employee_name="Private name never send", employee_user=self.users[0], company="_Test Company",
			status="Draft", currency="USD", invoice_date="2026-10-01", due_date="2026-10-16",
			period_start="2026-09-01", period_end="2026-09-30", calculation_method="Fixed Monthly",
			payee_name="Private payee never send", preferred_payment_method="Bank Transfer", bill_to_name="_Test Company"))
		doc.flags.invoice_api_action = True
		return doc

	def test_actual_leave_creation_and_open_edits_queue_once(self):
		frappe.get_doc(dict(doctype="Holiday List Assignment", assigned_to=self.employees[0],
			holiday_list="QA Calendar", from_date="2026-01-01", docstatus=1)).db_insert()
		with patch.object(frappe, "enqueue") as enqueue:
			doc = frappe.get_doc(dict(doctype="Leave Application", employee=self.employees[0],
				leave_type="Unpaid Leave", from_date="2026-10-05", to_date="2026-10-05",
				posting_date="2026-10-02", status="Open", leave_approver=self.users[2],
				follow_via_email=0, description="Private reason never send")).insert(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 1)
			self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
			doc.description = "Another private reason"
			doc.save(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 1)

	def test_actual_holiday_draft_and_submission_queue_once(self):
		with patch.object(frappe, "enqueue") as enqueue:
			doc = frappe.get_doc(dict(doctype="Employee Holiday", employee=self.employees[0],
				employee_name="Private name never send", year=2026, status="Draft",
				holidays=[dict(date="2026-10-05", description="Private holiday detail")])).insert(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 0)
			doc.status = "Submitted"; doc.save(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 1)
			doc.save(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 1)

	def test_actual_invoice_enters_review_once_per_submission(self):
		with patch.object(frappe, "enqueue") as enqueue:
			doc = self.invoice().insert(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 0)
			doc.status = "Pending HR Review"; doc.save(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 1)
			doc.save(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 1)
			first = enqueue.call_args.kwargs["payload"]["event_id"]
			doc.status = "Changes Requested"; doc.save(ignore_permissions=True)
			doc.status = "Pending HR Review"; doc.save(ignore_permissions=True)
			self.assertEqual(enqueue.call_count, 2)
			self.assertNotEqual(enqueue.call_args.kwargs["payload"]["event_id"], first)

	def test_real_enqueue_registers_only_after_commit_and_contains_no_private_fields(self):
		doc = self.invoice().insert(ignore_permissions=True)
		queue = MagicMock(); queue.count = 0
		with patch("frappe.utils.background_jobs.get_queue", return_value=queue), \
			patch("frappe.utils.background_jobs.get_job", return_value=None), \
			patch.object(type(frappe.db.after_commit), "add") as after_commit:
			mail.queue_review_email(doc)
			queue.enqueue_call.assert_not_called()
			after_commit.assert_called_once()
			after_commit.call_args.args[0]()
			kwargs = queue.enqueue_call.call_args.kwargs["kwargs"]["kwargs"]
			self.assertEqual(set(kwargs["payload"]), {"doctype", "name", "event_id"})
			self.assertNotIn("Private", str(kwargs))

	def test_actual_email_queue_is_minimal_fixed_recipient_and_replay_safe(self):
		doc = self.invoice().insert(ignore_permissions=True)
		# Delayed queue creation only; no SMTP worker runs on this isolated QA site.
		if not frappe.db.exists("Email Account", "QA Mail Queue"):
			frappe.get_doc(dict(doctype="Email Account", name="QA Mail Queue", email_account_name="QA Mail Queue",
				email_id="alerts@qa.invalid", enable_outgoing=1, default_outgoing=1,
				smtp_server="mail.qa.invalid", smtp_port=2525, no_smtp_authentication=1,
				always_use_account_email_id_as_sender=1)).db_insert()
		payload = mail.review_payload(doc)
		with patch.object(mail, "HR_REVIEW_EMAIL", self.users[2]):
			mail.send_review_email(payload)
			mail.send_review_email(payload)
		queues = frappe.get_all("Email Queue", filters={"reference_doctype": doc.doctype, "reference_name": doc.name}, pluck="name")
		self.assertEqual(len(queues), 1)
		queued = frappe.get_doc("Email Queue", queues[0])
		self.assertEqual([row.recipient for row in queued.recipients], [self.users[2]])
		message = Parser(policy=policy.default).parsestr(queued.message)
		body = message.get_body(preferencelist=("html",)).get_content()
		self.assertIn("/desk/employee-invoice/", body)
		self.assertNotIn("Private", body)
		self.assertFalse(json.loads(queued.attachments or "[]"))

	def test_missing_document_does_not_send_and_fixed_inbox_cannot_be_overridden(self):
		payload = {"doctype": "Employee Invoice", "name": "QA-ABSENT", "event_id": "missing"}
		with patch.object(frappe, "sendmail") as sendmail:
			mail.send_review_email(payload); sendmail.assert_not_called()
		doc = self.invoice().insert(ignore_permissions=True)
		payload = {**mail.review_payload(doc), "recipients": ["unrelated@qa.invalid"]}
		with patch.object(frappe, "sendmail") as sendmail:
			mail.send_review_email(payload)
			self.assertEqual(sendmail.call_args.kwargs["recipients"], ["hr@realtyna.com"])
			self.assertTrue(sendmail.call_args.kwargs["delayed"])
			self.assertFalse(sendmail.call_args.kwargs["now"])
