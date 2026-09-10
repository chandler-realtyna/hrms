import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


LEGACY_SALARY_FIELDS = (
	"ctc",
	"salary_currency",
	"salary_mode",
	"employee_advance_account",
	"salary_cb",
	"payroll_cost_center",
)


def execute():
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "custom_invoice_calculation_method",
					"fieldtype": "Select",
					"label": "Invoice Calculation Method",
					"options": "\nFixed Monthly\nHourly",
					"insert_after": "salary_mode",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_invoice_currency",
					"fieldtype": "Link",
					"label": "Invoice Currency",
					"options": "Currency",
					"insert_after": "custom_invoice_calculation_method",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_monthly_invoice_amount",
					"fieldtype": "Currency",
					"label": "Monthly Invoice Amount",
					"options": "custom_invoice_currency",
					"insert_after": "custom_invoice_currency",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_invoice_hourly_rate",
					"fieldtype": "Currency",
					"label": "Invoice Hourly Rate",
					"options": "custom_invoice_currency",
					"insert_after": "custom_monthly_invoice_amount",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_invoice_payee_name",
					"fieldtype": "Data",
					"label": "Invoice Legal Payee Name",
					"insert_after": "custom_invoice_hourly_rate",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_invoice_payee_address",
					"fieldtype": "Small Text",
					"label": "Invoice Payee Address",
					"insert_after": "custom_invoice_payee_name",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_preferred_payment_method",
					"fieldtype": "Select",
					"label": "Preferred Payment Method",
					"options": "\nBank Transfer\nCash\nOnline Payment Service\nCryptocurrency\nOther",
					"insert_after": "custom_invoice_payee_address",
					"permlevel": 0,
				},
				{
					"fieldname": "custom_invoice_payment_details",
					"fieldtype": "Small Text",
					"label": "Invoice Payment Details",
					"description": "Account, wallet, service, network, or other payout instructions.",
					"insert_after": "custom_preferred_payment_method",
					"permlevel": 0,
				},
			],
		},
		update=True,
	)
	for fieldname in LEGACY_SALARY_FIELDS:
		make_property_setter(
			"Employee",
			fieldname,
			"hidden",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype="Employee")
