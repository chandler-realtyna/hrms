from frappe.utils import add_days, getdate, nowdate


PAYMENT_TERM_DAYS = 15
FINAL_INVOICE_STATES = {"Approved for Payment", "Paid", "Cancelled"}


def invoice_defaults():
	issue_date = getdate(nowdate())
	return {"invoice_date": str(issue_date), "due_date": str(add_days(issue_date, PAYMENT_TERM_DAYS))}


def apply_invoice_terms(doc):
	# Preserve already-approved financial history; no bulk backfill is implied.
	if not doc.is_new() and doc.status in FINAL_INVOICE_STATES:
		return
	doc.invoice_date = doc.invoice_date or nowdate()
	doc.due_date = add_days(getdate(doc.invoice_date), PAYMENT_TERM_DAYS)
