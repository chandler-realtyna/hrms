frappe.listview_settings["Leave Application"] = {
	add_fields: [
		"leave_type",
		"employee",
		"employee_name",
		"total_leave_days",
		"from_date",
		"to_date",
	],
	has_indicator_for_draft: 1,
	get_indicator: function (doc) {
		const status_color = {
			Approved: "green",
			Rejected: "red",
			Open: "orange",
			Draft: "red",
			Cancelled: "red",
			Submitted: "blue",
		};
		if (!doc.docstatus && ["Approved", "Rejected"].includes(doc.status)) {
			const label = doc.status === "Approved"
				? __("Approved · Awaiting confirmation")
				: __("Rejected · Awaiting confirmation");
			return [label, "orange", "docstatus,=,0|status,=," + doc.status];
		}
		return [__(doc.status), status_color[doc.status], "status,=," + doc.status];
	},
};
