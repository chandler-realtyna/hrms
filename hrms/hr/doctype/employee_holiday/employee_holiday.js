// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Holiday", {
	refresh(frm) {
		frm.trigger("set_action_buttons")
	},

	set_action_buttons(frm) {
		// Clear any previously added custom buttons
		frm.clear_custom_buttons()

		const isHR = frappe.user.has_role(["HR Manager", "HR User", "System Manager"])

		// ── Employee: Submit button ──────────────────────────────────────────
		if (frm.doc.status === "Draft" && !frm.is_new()) {
			frm.add_custom_button(__("Submit for Approval"), () => {
				if ((frm.doc.holidays || []).length !== 15) {
					frappe.msgprint({
						title: __("Cannot Submit"),
						message: __(
							"You must select exactly 15 holiday dates before submitting. Currently selected: {0}",
							[frm.doc.holidays ? frm.doc.holidays.length : 0]
						),
						indicator: "red",
					})
					return
				}
				frappe.confirm(
					__("Submit these {0} holidays for HR approval?", [
						(frm.doc.holidays || []).length,
					]),
					() => {
						frappe.call({
							method: "hrms.api.submit_employee_holidays",
							args: { name: frm.doc.name },
							callback(r) {
								if (!r.exc) {
									frm.reload_doc()
									frappe.show_alert({
										message: __("Holidays submitted for approval"),
										indicator: "green",
									})
								}
							},
						})
					}
				)
			}).addClass("btn-primary")
		}

		// ── HR: Approve / Reject buttons ─────────────────────────────────────
		if (frm.doc.status === "Submitted" && isHR) {
			frm.add_custom_button(__("Approve"), () => {
				frappe.confirm(
					__("Approve holidays for {0}? A Holiday List will be created automatically.", [
						frm.doc.employee_name,
					]),
					() => {
						frappe.call({
							method: "hrms.api.approve_employee_holiday",
							args: { name: frm.doc.name },
							callback(r) {
								if (!r.exc) {
									frm.reload_doc()
									frappe.show_alert({
										message: __(
											"Approved! Holiday List '{0}' created.",
											[r.message.holiday_list]
										),
										indicator: "green",
									})
								}
							},
						})
					}
				)
			}).addClass("btn-success")

			frm.add_custom_button(__("Reject"), () => {
				frappe.confirm(
					__("Reject the holiday request from {0}?", [frm.doc.employee_name]),
					() => {
						frappe.call({
							method: "hrms.api.reject_employee_holiday",
							args: { name: frm.doc.name },
							callback(r) {
								if (!r.exc) {
									frm.reload_doc()
									frappe.show_alert({
										message: __("Request rejected"),
										indicator: "orange",
									})
								}
							},
						})
					}
				)
			}).addClass("btn-danger")
		}

		// ── Status indicator colour ──────────────────────────────────────────
		const colours = {
			Draft: "grey",
			Submitted: "yellow",
			Approved: "green",
			Rejected: "red",
		}
		frm.set_indicator_formatter("status", (doc) => colours[doc.status] || "grey")

		// Make status and holiday_list read-only in the form
		frm.set_df_property("status", "read_only", 1)
		frm.set_df_property("holiday_list", "read_only", 1)

		// Lock the whole form once submitted (employees can't edit)
		const userIsEmployee =
			!frappe.user.has_role(["HR Manager", "HR User", "System Manager"]) &&
			frappe.user.name !== "Administrator"

		if (frm.doc.status !== "Draft" && userIsEmployee) {
			frm.disable_form()
		}
	},
})
