"""Minimal HR inbox alerts after commit, replay-safe in the existing mail queue."""
import hashlib
from html import escape
from urllib.parse import quote

import frappe
from frappe import _

HR_REVIEW_EMAIL = "hr@realtyna.com"
REVIEW_TYPES = {
	"Leave Application": ("Leave request", "leave-application"),
	"Employee Holiday": ("Holiday request", "employee-holiday"),
	"Employee Invoice": ("Invoice", "employee-invoice"),
}


def review_payload(doc):
	if doc.doctype not in REVIEW_TYPES:
		raise ValueError("Unsupported review notification")
	event_id = hashlib.sha256(f"{doc.doctype}|{doc.name}|{doc.modified}|{doc.status}".encode()).hexdigest()
	return {"doctype": doc.doctype, "name": doc.name, "event_id": event_id}


def queue_review_email(doc):
	payload = review_payload(doc)
	frappe.enqueue("hrms.utils.review_notifications.send_review_email", queue="short",
		enqueue_after_commit=True, job_id=f"hr-review-{payload['event_id']}", deduplicate=True, payload=payload)


def send_review_email(payload):
	doctype, name = payload["doctype"], payload["name"]
	if doctype not in REVIEW_TYPES:
		raise ValueError("Unsupported review notification")
	# Lock the reference while checking replay; the business document is unchanged.
	if not frappe.db.get_value(doctype, name, "name", for_update=True):
		return
	message_id = f"hrms-review-{payload['event_id']}@realtyna.com"
	if frappe.db.exists("Email Queue", {"message_id": message_id}):
		return
	label, route = REVIEW_TYPES[doctype]
	url = frappe.utils.get_url(f"/desk/{route}/{quote(name, safe='')}")
	message = '<p>{}</p><p><a href="{}">{}</a></p>'.format(
		escape(_("{0} is ready for review.").format(_(label))), escape(url, quote=True), escape(_("Open request")))
	sender = frappe.db.get_value("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}, "email_id") or HR_REVIEW_EMAIL
	frappe.sendmail(recipients=[HR_REVIEW_EMAIL], sender=f"Realtyna HRMS <{sender}>", subject=_("{0} needs review").format(_(label)),
		message=message, message_id=message_id, reference_doctype=doctype, reference_name=name,
		delayed=True, now=False)
