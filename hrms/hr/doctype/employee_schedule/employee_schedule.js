// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Schedule", {
	refresh(frm) {
		frm.trigger("set_action_buttons")
	},

	set_action_buttons(frm) {
		frm.clear_custom_buttons()
		const isHR = frappe.user.has_role(["HR Manager", "HR User", "System Manager"])
		const submitForApproval = async () => {
			if (frm.is_dirty()) {
				const previousStatus = frm.doc.status
				if (previousStatus === "Approved") await frm.set_value("status", "Submitted")
				if (previousStatus === "Rejected") await frm.set_value("status", "Draft")
				try {
					await frm.save()
				} catch (error) {
					await frm.set_value("status", previousStatus)
					throw error
				}
			}
			if (frm.doc.status !== "Submitted") {
				await frappe.call({method: "hrms.api.submit_employee_schedule", args: {name: frm.doc.name}})
			}
			await frm.reload_doc()
			frappe.show_alert({message: __("Schedule submitted"), indicator: "green"})
		}

		if (["Draft", "Rejected", "Approved"].includes(frm.doc.status) && !frm.is_new()) {
			const label = frm.doc.status === "Approved"
				? __("Request Change Approval")
				: frm.doc.status === "Rejected" ? __("Resubmit for Approval") : __("Submit for Approval")
			frm.add_custom_button(label, () => {
				frappe.confirm(__("Submit this schedule for HR approval?"), submitForApproval)
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
		// Employees keep edit access after first submit (Draft, Rejected,
		// Approved and Submitted are all editable — server-side validation
		// routes Approved/Submitted edits back through HR approval).
	},
})
