frappe.ui.form.on("Employee Invoice", {
	refresh(frm) {
		frm.disable_save();
		frm.clear_custom_buttons();
		const is_hr = frappe.session.user === "Administrator" || frappe.user.has_role(["HR Manager", "HR User", "System Manager", "Company Desk Administrator"]);
		if (frm.is_new() || !is_hr) return;
		const invoke = async (method, args = {}) => {
			const response = await frappe.call({ method: `hrms.api.employee_invoice.${method}`, args: { name: frm.doc.name, ...args }, freeze: true });
			await frm.reload_doc();
			if (response.message?.needs_employee_confirmation) frappe.msgprint(__("Invoice data changed. Employee confirmation is required again."));
		};
		if (frm.doc.status === "Pending HR Review") {
			frm.add_custom_button(__("Approve for Payment"), () => frappe.confirm(__("Approve this invoice for payment?"), () => invoke("hr_approve_employee_invoice")), __("Review"));
		}
		if (["Pending HR Review", "Pending Employee Confirmation"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Return for Correction"), () => frappe.prompt([
				{ fieldname: "reason", label: __("Correction Reason"), fieldtype: "Small Text", reqd: 1 },
			], values => invoke("hr_return_employee_invoice", values), __("Return Invoice")), __("Review"));
		}
		if (!["Draft", "Approved for Payment", "Paid", "Cancelled"].includes(frm.doc.status)) {
			for (const field of ["currency", "monthly_amount", "hourly_rate"]) frm.set_df_property(field, "read_only", 0);
			frm.add_custom_button(__("Save HR Changes"), () => frappe.prompt([
				{ fieldname: "reason", label: __("Reason for Changes"), fieldtype: "Small Text", reqd: 1 },
			], ({ reason }) => {
				const fields = ["due_date", "period_start", "period_end", "due_hours", "payee_name", "payee_address", "preferred_payment_method", "payment_details", "bank_name", "bank_account_no", "iban", "employee_note", "monthly_amount", "hourly_rate", "currency", "hr_note", "adjustments"];
				const values = Object.fromEntries(fields.map(field => [field, frm.doc[field]]));
				return invoke("hr_update_employee_invoice", { values, reason });
			}, __("Save HR Changes")), __("Review"));
		}
		if (frm.doc.status === "Approved for Payment") {
			frm.add_custom_button(__("Mark Paid"), () => frappe.prompt([
				{ fieldname: "payment_method", label: __("Payment Method"), fieldtype: "Select", options: "Bank Transfer\nCash\nOnline Payment Service\nCryptocurrency\nOther", reqd: 1 },
				{ fieldname: "payment_date", label: __("Payment Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
				{ fieldname: "payment_reference", label: __("Payment Reference"), fieldtype: "Data", reqd: 1 },
			], values => invoke("mark_employee_invoice_paid", values), __("Record Payment")), __("Review"));
		}
	},
});
