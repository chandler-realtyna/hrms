frappe.ui.form.on("Employee Invoice", {
	refresh(frm) {
		frm.__invoice_review_token = null;
		frm.disable_save();
		frm.clear_custom_buttons();
		const is_hr = frappe.session.user === "Administrator" || frappe.user.has_role(["HR Manager", "HR User", "System Manager", "Company Desk Administrator"]);
		employee_invoice_render_review(frm, is_hr && !frm.is_new() ? undefined : {
			ready: Boolean(Number(frm.doc.time_approval_ready)),
			unfinalized_count: new Set((frm.doc.time_summary || []).filter(row => row.approval_status !== "Finalized").map(row => row.timesheet)).size,
		});
		if (frm.is_new() || !is_hr) return;
		const invoke = async (method, args = {}) => {
			const response = await frappe.call({ method: `hrms.api.employee_invoice.${method}`, args: { name: frm.doc.name, ...args }, freeze: true });
			await frm.reload_doc();
			if (response.message?.needs_employee_confirmation) frappe.msgprint(__("Invoice data changed. Employee confirmation is required again."));
		};
		if (frm.doc.status === "Pending HR Review") {
			let approval_ready = false;
			const approve = frm.add_custom_button(__("Approve for Payment"), () => {
				if (!approval_ready) {
					frappe.msgprint(__("Timesheet finalization must be checked and complete before approving this invoice."));
					return;
				}
				frappe.confirm(__("Approve this invoice for payment?"), () => invoke("hr_approve_employee_invoice"));
			}, __("Review"));
			approve.prop("disabled", true).addClass("disabled").attr({"aria-disabled": "true", title: __("Checking timesheet finalization")});
			const review_token = {};
			frm.__invoice_review_token = review_token;
			frappe.call({
				method: "hrms.api.employee_invoice.get_employee_invoice_review_readiness",
				args: { name: frm.doc.name },
				callback(response) {
					if (frm.__invoice_review_token !== review_token || frm.doc.status !== "Pending HR Review") return;
					const readiness = response.message;
					if (!readiness) return;
					approval_ready = Boolean(readiness.ready);
					approve.prop("disabled", !approval_ready).toggleClass("disabled", !approval_ready).attr("aria-disabled", String(!approval_ready)).attr("title", readiness.ready ? "" : __("Finalize the referenced timesheets before approving this invoice."));
					employee_invoice_render_review(frm, readiness);
				},
				error() {
					if (frm.__invoice_review_token !== review_token) return;
					employee_invoice_render_review(frm, { unavailable: true });
				},
			});
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

// Display only: persisted hours remain numeric inputs to the invoice calculations.
function employee_invoice_duration(value) {
	const hours = Number(value || 0);
	if (!Number.isFinite(hours)) return __("Unavailable");
	const minutes = Math.round(Math.abs(hours) * 60);
	if (hours !== 0 && minutes === 0) return __("Under 1 minute");
	const text = __("{0}h {1}m", [Math.floor(minutes / 60), minutes % 60]);
	return hours < 0 ? `−${text}` : text;
}

function employee_invoice_render_review(frm, readiness) {
	const doc = frm.doc;
	const escape = value => frappe.utils.escape_html(String(value ?? ""));
	const actions = {
		Draft: __("The employee must complete and confirm the invoice."),
		"Changes Requested": __("The employee must correct and confirm the invoice again."),
		"Pending Employee Confirmation": __("Wait for the employee to confirm the updated invoice."),
		"Approved for Payment": __("Arrange payment, then record its date, method and reference."),
		Paid: __("Payment has been recorded. Review the payment record and history below."),
		Cancelled: __("This invoice is cancelled; no payment action is required."),
	};
	let action = actions[doc.status] || __("Review the invoice status before taking action.");
	let color = ["Paid", "Approved for Payment"].includes(doc.status) ? "green" : "orange";
	if (doc.status === "Pending HR Review") {
		if (readiness?.unavailable) action = __("Timesheet readiness could not be checked. Reload this invoice to try again.");
		else if (!readiness) action = __("Checking whether the referenced timesheets are finalized.");
		else if (readiness.ready) {
			action = __("Review the amount and recipient details, then approve for payment. Approval rechecks the current invoice and employee confirmation.");
			color = "green";
		} else action = __("{0} referenced timesheet(s) are not finalized. Complete timesheet review before approving this invoice.", [readiness.unfinalized_count]);
	}
	const total = frappe.format(doc.grand_total || 0, { fieldtype: "Currency", options: "currency" }, { inline: true }, doc);
	const period = doc.period_start && doc.period_end ? `${frappe.datetime.str_to_user(doc.period_start)} – ${frappe.datetime.str_to_user(doc.period_end)}` : __("Period not set");
	frm.fields_dict.review_overview?.$wrapper.html(`
		<div class="mb-3">
			<div class="mb-2"><span class="indicator-pill ${color}">${escape(__(doc.status || "Draft"))}</span></div>
			<p class="mb-2"><strong>${escape(__("Next action"))}:</strong> ${escape(action)}</p>
			<div class="text-muted">${escape(doc.employee_name || doc.employee || "")} · ${escape(doc.company || "")} · ${escape(period)}</div>
			<div class="mt-2"><strong>${escape(__("Invoice total"))}: ${total}</strong> · ${escape(__("Worked time"))}: ${escape(employee_invoice_duration(doc.worked_hours))}</div>
		</div>`);
	for (const field of ["worked_hours", "paid_leave_hours", "sick_leave_hours", "unpaid_leave_hours", "payable_hours"]) {
		frm.set_df_property(field, "formatter", employee_invoice_duration);
		frm.refresh_field(field);
	}
	frm.set_df_property("leave_summary", "formatter", value => escape(value || "").replace(/\((\d+(?:\.\d+)?) hours\)/g, (_, hours) => `(${escape(employee_invoice_duration(hours))})`).replace(/\n/g, "<br>"));
	frm.refresh_field("leave_summary");
	const hours_field = frappe.meta.get_docfield("Employee Invoice Time Summary", "hours", doc.name);
	if (hours_field) hours_field.formatter = employee_invoice_duration;
	frm.refresh_field("time_summary");
}
