// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Timesheet", {
	refresh(frm) {
		if (frm.doc.custom_is_weekly) {
			frm.trigger("setup_weekly_timesheet_actions");
		}

		if (frm.doc.docstatus === 1 && frappe.model.can_create("Salary Slip")) {
			if (!frm.doc.salary_slip && frm.doc.employee) {
				frm.add_custom_button(__("Create Salary Slip"), function () {
					frm.trigger("make_salary_slip");
				});
			}
		}
	},

	setup_weekly_timesheet_actions(frm) {
		const status = frm.doc.custom_weekly_status;
		const is_hr = frappe.user_roles.some((role) => ["HR Manager", "HR User"].includes(role));

		if (!["Draft", "Correction Required"].includes(status)) {
			frm.disable_save();
			frm.set_df_property("time_logs", "read_only", 1);
			frm.set_df_property("note", "read_only", 1);
		}

		if (frm.doc.docstatus === 0 && status === "Pending HR Review" && is_hr) {
			frm.add_custom_button(__("Approve & Close Week"), () => {
				frappe.confirm(
					__("Close this weekly timesheet? It will be locked from direct editing."),
					() => frm.call({
						method: "hrms.api.weekly_timesheet.hr_close_weekly_timesheet",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Closing weekly timesheet..."),
						callback: () => frm.reload_doc(),
					})
				);
			}, __("Weekly Approval"));

			frm.add_custom_button(__("Return for Correction"), () => {
				frappe.prompt(
					{
						fieldname: "reason",
						fieldtype: "Small Text",
						label: __("Return Reason"),
						reqd: 1,
					},
					(values) => frm.call({
						method: "hrms.api.weekly_timesheet.hr_return_weekly_timesheet",
						args: { name: frm.doc.name, reason: values.reason },
						freeze: true,
						callback: () => frm.reload_doc(),
					}),
					__("Return Weekly Timesheet")
				);
			}, __("Weekly Approval"));
		}
	},

	make_salary_slip: function (frm) {
		frappe.model.open_mapped_doc({
			method: "hrms.payroll.doctype.salary_slip.salary_slip.make_salary_slip_from_timesheet",
			frm: frm,
		});
	},
});
