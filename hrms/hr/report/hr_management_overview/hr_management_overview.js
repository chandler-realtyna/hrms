// Copyright (c) 2026, Realtyna Inc. and contributors
// For license information, please see license.txt

frappe.query_reports["HR Management Overview"] = {
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
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(),
			reqd: 1,
		},
		{
			fieldname: "preview_demo_data",
			label: __("Preview Fictional Data"),
			fieldtype: "Check",
			default: 0,
			description: __("Shows isolated sample values without creating operational records."),
		},
	],
}
