"""Stable personal-calendar identity; never rewrite another employee's calendar."""
import hashlib

import frappe
from frappe import _


def personal_calendar_name(employee, year):
	name = f"Employee holidays - {employee} - {int(year)}"
	if len(name) <= 140:
		return name
	digest = hashlib.sha256(employee.encode()).hexdigest()[:12]
	return f"Employee holidays - {employee[:90]} - {digest} - {int(year)}"


def ensure_calendar_not_shared(name, employee):
	checks = [
		("Employee Holiday", {"holiday_list": name, "employee": ["!=", employee]}),
		("Holiday List Assignment", {"holiday_list": name, "assigned_to": ["!=", employee], "docstatus": ["<", 2]}),
	]
	for doctype, field, extra in [
		("Employee", "holiday_list", {"name": ["!=", employee]}),
		("Company", "default_holiday_list", {}),
	]:
		if frappe.get_meta(doctype).has_field(field):
			checks.append((doctype, {field: name, **extra}))
	for doctype, filters in checks:
		if frappe.db.exists(doctype, filters):
			frappe.throw(_("This personal holiday calendar is shared. HR must review its assignments before it can be changed."))
