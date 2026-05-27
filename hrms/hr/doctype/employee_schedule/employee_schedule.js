// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Schedule", {
	refresh(frm) {
		frm.trigger("set_action_buttons")
	},

	set_action_buttons(frm) {
		frm.clear_custom_buttons()
		const isHR = frappe.user.has_role(["HR Manager", "HR User", "System Manager"])

		if (frm.doc.status === "Draft" && !frm.is_new()) {
			frm.add_custom_button(__("Submit for Approval"), () => {
				frappe.confirm(__("Submit this schedule for HR approval?"), () => {
					frappe.call({
						method: "hrms.api.submit_employee_schedule",
						args: { name: frm.doc.name },
						callback(r) {
							if (!r.exc) {
								frm.reload_doc()
								frappe.show_alert({ message: __("Schedule submitted"), indicator: "green" })
							}
						},
					})
				})
			}).addClass("btn-primary")
		}

		if (frm.doc.status === "Submitted" && isHR) {
			frm.add_custom_button(__("Approve"), () => {
				frappe.confirm(__("Approve schedule for {0}?", [frm.doc.employee_name]), () => {
					frappe.call({
						method: "hrms.api.approve_employee_schedule",
						args: { name: frm.doc.name },
						callback(r) {
							if (!r.exc) {
								frm.reload_doc()
								frappe.show_alert({ message: __("Schedule approved"), indicator: "green" })
							}
						},
					})
				})
			}).addClass("btn-success")

			frm.add_custom_button(__("Reject"), () => {
				frappe.confirm(__("Reject this schedule?"), () => {
					frappe.call({
						method: "hrms.api.reject_employee_schedule",
						args: { name: frm.doc.name },
						callback(r) {
							if (!r.exc) {
								frm.reload_doc()
								frappe.show_alert({ message: __("Schedule rejected"), indicator: "orange" })
							}
						},
					})
				})
			}).addClass("btn-danger")
		}

		frm.set_df_property("status", "read_only", 1)
		const userIsEmployee =
			!frappe.user.has_role(["HR Manager", "HR User", "System Manager"]) &&
			frappe.user.name !== "Administrator"
		if (frm.doc.status !== "Draft" && userIsEmployee) {
			frm.disable_form()
		}
	},
})
