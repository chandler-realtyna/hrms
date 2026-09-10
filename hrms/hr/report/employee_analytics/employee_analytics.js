// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Employee Analytics"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "parameter",
			label: __("Parameter"),
			fieldtype: "Select",
			options: ["Branch", "Grade", "Department", "Designation", "Employment Type"],
			default: "Department",
			reqd: 1,
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "status",
			label: __("Employee Status"),
			fieldtype: "Select",
			options: ["", "Active", "Suspended", "Left"],
			default: "Active",
		},
	],
};
