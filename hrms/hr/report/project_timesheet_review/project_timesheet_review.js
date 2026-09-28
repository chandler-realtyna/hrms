// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Project Timesheet Review"] = {
	filters: [
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "project_lead",
			label: __("Project Lead"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "week_start",
			label: __("Week Start"),
			fieldtype: "Date",
		},
		{
			fieldname: "project_status",
			label: __("Project Status"),
			fieldtype: "Select",
			options: "\nPending\nApproved\nReturned\nHR Review",
		},
		{
			fieldname: "hr_status",
			label: __("HR Status"),
			fieldtype: "Select",
			options: "\nDraft\nPending Project Approval\nCorrection Required\nPending HR Review\nClosed",
		},
	],

	onload(report) {
		const pending_rows = () =>
			(frappe.query_report.data || []).filter((r) => r.project_status === "Pending");

		report.page.add_inner_button(__("Approve pending (filtered)"), async () => {
			const rows = pending_rows();
			if (!rows.length) {
				frappe.msgprint(__("No pending sections in the current filter."));
				return;
			}
			let ok = 0;
			const failed = [];
			for (const row of rows) {
				try {
					await frappe.call({
						method: "hrms.api.weekly_timesheet.approve_project_review",
						args: { approval_name: row.approval_name },
					});
					ok++;
				} catch (e) {
					failed.push(row.project + " / " + row.employee_name);
				}
			}
			frappe.query_report.refresh();
			if (failed.length) {
				frappe.msgprint(
					__("Approved {0} section(s). Could not approve: {1}.", [ok, failed.join(", ")])
				);
			} else {
				frappe.msgprint(__("Approved {0} section(s).", [ok]));
			}
		});

		report.page.add_inner_button(__("Return pending (filtered)"), () => {
			const rows = pending_rows();
			if (!rows.length) {
				frappe.msgprint(__("No pending sections in the current filter."));
				return;
			}
			frappe.prompt(
				{
					fieldname: "reason",
					label: __("Return reason"),
					fieldtype: "Small Text",
					reqd: 1,
				},
				async ({ reason }) => {
					let ok = 0;
					const failed = [];
					for (const row of rows) {
						try {
							await frappe.call({
								method: "hrms.api.weekly_timesheet.review_project_approval",
								args: { approval_name: row.approval_name, action: "return", reason },
							});
							ok++;
						} catch (e) {
							failed.push(row.project + " / " + row.employee_name);
						}
					}
					frappe.query_report.refresh();
					if (failed.length) {
						frappe.msgprint(
							__("Returned {0} section(s). Could not return: {1}.", [ok, failed.join(", ")])
						);
					} else {
						frappe.msgprint(__("Returned {0} section(s).", [ok]));
					}
				},
				__("Return for correction"),
				__("Return")
			);
		});
	},
};
