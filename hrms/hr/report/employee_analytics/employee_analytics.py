# Copyright (c) 2026, Realtyna Inc. and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _


PARAMETER_FIELDS = {
	"Branch": "branch",
	"Grade": "grade",
	"Department": "department",
	"Designation": "designation",
	"Employment Type": "employment_type",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.company:
		frappe.throw(_("Company is mandatory"))

	parameter = filters.parameter or "Department"
	parameter_field = PARAMETER_FIELDS.get(parameter)
	if not parameter_field:
		frappe.throw(_("Unsupported analytics parameter."))

	employees = _employees(filters)
	chart, category_count, missing_count = _chart(employees, parameter_field)
	summary = [
		{"value": len(employees), "label": _("Employees"), "datatype": "Int"},
		{"value": category_count, "label": _(parameter), "datatype": "Int"},
		{
			"value": missing_count,
			"label": _("Missing {0}").format(_(parameter)),
			"datatype": "Int",
			"indicator": "Orange" if missing_count else "Green",
		},
	]
	return _columns(), employees, None, chart, summary


def _columns():
	return [
		{
			"fieldname": "name",
			"label": _("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			"width": 140,
		},
		{"fieldname": "employee_name", "label": _("Name"), "fieldtype": "Data", "width": 200},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 100},
		{
			"fieldname": "department",
			"label": _("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"width": 170,
		},
		{
			"fieldname": "designation",
			"label": _("Designation"),
			"fieldtype": "Link",
			"options": "Designation",
			"width": 170,
		},
		{
			"fieldname": "employment_type",
			"label": _("Employment Type"),
			"fieldtype": "Link",
			"options": "Employment Type",
			"width": 140,
		},
		{"fieldname": "date_of_joining", "label": _("Joined"), "fieldtype": "Date", "width": 110},
		{
			"fieldname": "branch",
			"label": _("Branch"),
			"fieldtype": "Link",
			"options": "Branch",
			"width": 130,
		},
	]


def _employees(filters):
	db_filters = {"company": filters.company}
	if filters.status:
		db_filters["status"] = filters.status
	if filters.department:
		db_filters["department"] = filters.department

	return frappe.get_list(
		"Employee",
		filters=db_filters,
		fields=[
			"name",
			"employee_name",
			"status",
			"department",
			"designation",
			"employment_type",
			"date_of_joining",
			"branch",
			"grade",
		],
		order_by="employee_name asc",
		limit_page_length=500,
	)


def _chart(employees, fieldname):
	counts = Counter((row.get(fieldname) or _("Not Set")) for row in employees)
	ordered = sorted(counts.items(), key=lambda item: (-item[1], str(item[0]).lower()))
	chart = {
		"data": {
			"labels": [label for label, _count in ordered],
			"datasets": [
				{"name": _("Employees"), "values": [count for _label, count in ordered]}
			],
		},
		"type": "donut",
	}
	missing_label = _("Not Set")
	missing_count = counts.get(missing_label, 0)
	category_count = len([label for label in counts if label != missing_label])
	return chart, category_count, missing_count
