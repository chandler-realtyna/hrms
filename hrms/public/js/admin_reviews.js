frappe.pages["admin-reviews"].on_page_load = function (wrapper) {
	wrapper.admin_reviews = new HRMSAdminReviews(wrapper);
};
frappe.pages["admin-reviews"].on_page_show = function (wrapper) {
	wrapper.admin_reviews.show();
};

class HRMSAdminReviews {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Admin Reviews"), single_column: true });
		this.content = $('<div class="admin-reviews-page"></div>').appendTo(this.page.main);
		this.page.set_secondary_action(__("Admin Reviews"), () => frappe.set_route("admin-reviews"), "home");
		this.page.set_primary_action(__("Refresh"), () => this.show(), "refresh");
	}
	async call(method, args = {}) {
		const response = await frappe.call({ method: `hrms.api.${method}`, args });
		return response.message;
	}
	async show() {
		if (frappe.boot.hrms_admin_sidebar && frappe.app.sidebar?.sidebar_title !== "Admin Reviews") {
			frappe.app.sidebar.setup("Admin Reviews");
		}
		const mode = frappe.get_route()[1] || "home";
		const version = this.version = (this.version || 0) + 1;
		this.content.empty().append($('<div class="admin-reviews-loading"></div>').text(__("Loading")));
		try {
			const sections = await this.call("admin_desk.get_admin_desk_sections");
			if (version !== this.version) return;
			this.content.empty();
			if (mode === "home") {
				this.page.set_title(__("Admin Reviews"));
				this.home(sections);
				return;
			}
			const item = sections.flatMap(section => section.items).find(item => item.route === `/desk/admin-reviews/${mode}`);
			if (!item) throw new Error(__("You do not have access to this review queue."));
			this.page.set_title(__(item.label));
			const methods = { "project-timesheets": "get_project_review_queue", "project-reports": "get_project_approval_queue", "hr-timesheets": "get_hr_weekly_timesheet_queue" };
			const rows = await this.call(`weekly_timesheet.${methods[mode]}`);
			if (version !== this.version) return;
			this.content.empty();
			if (!rows.length) this.content.append($('<div class="admin-reviews-empty"></div>').text(__("Nothing waiting for review")));
			else if (mode === "project-reports") this.reports(rows);
			else this.queue(rows, mode);
		} catch (error) {
			if (version === this.version) this.content.empty().append($('<div class="alert alert-danger"></div>').text(error.message || __("Could not load this review queue.")));
		}
	}
	home(sections) {
		sections.forEach(section => {
			const band = $('<section class="admin-reviews-section"></section>').appendTo(this.content);
			$("<h3 class='admin-reviews-heading'></h3>").text(__(section.label)).appendTo(band);
			const grid = $("<div class='admin-reviews-grid'></div>").appendTo(band);
			section.items.forEach(item => {
				const link = $("<a class='admin-reviews-link'></a>").attr("href", item.route).appendTo(grid);
				$("<span class='admin-reviews-link-label'></span>").text(__(item.label)).appendTo(link);
				$("<span class='admin-reviews-link-icon'></span>").html(frappe.utils.icon("right", "sm")).appendTo(link);
				link.on("click", event => {
					if (event.ctrlKey || event.metaKey || event.shiftKey) return;
					event.preventDefault();
					if (item.doctype) {
						frappe.route_options = item.filters || {};
						frappe.set_route("List", item.doctype);
					} else frappe.set_route("admin-reviews", item.route.split("/").pop());
				});
			});
		});
	}
	table(parent, headings) {
		const table = $('<table class="table admin-reviews-table"></table>').appendTo($('<div class="admin-reviews-table-scroll"></div>').appendTo(parent));
		const header = $("<tr></tr>").appendTo($("<thead></thead>").appendTo(table));
		headings.forEach(label => $("<th></th>").text(__(label)).appendTo(header));
		return $("<tbody></tbody>").appendTo(table);
	}
	button(parent, label, action, primary = false) {
		return $('<button type="button" class="btn btn-sm"></button>').addClass(primary ? "btn-primary" : "btn-default").text(__(label)).appendTo(parent)
			.on("click", async function () {
				$(this).prop("disabled", true);
				try { await action(); } finally { $(this).prop("disabled", false); }
			});
	}
	queue(rows, mode) {
		const hr = mode === "hr-timesheets";
		const selected = new Set();
		const toolbar = $('<div class="admin-reviews-toolbar"></div>').appendTo(this.content);
		if (!hr) this.button(toolbar, "Approve selected sections", async () => {
			if (!selected.size) return frappe.msgprint(__("Select pending sections first."));
			frappe.confirm(__("Approve {0} selected project sections?", [selected.size]), async () => {
				try { for (const approval_name of selected) await this.call("weekly_timesheet.approve_project_review", { approval_name }); }
				finally { await this.show(); }
			});
		}, true);
		const body = this.table(this.content, hr ? ["Employee", "Week", "Hours", "Action"] : ["", "Employee", "Project", "Week", "Hours", "Status", "Action"]);
		rows.forEach(row => {
			const tr = $("<tr></tr>").appendTo(body);
			if (!hr) {
				const cell = $("<td></td>").appendTo(tr);
				if (row.actionable) $('<input type="checkbox">').attr("aria-label", __("Select section for {0}", [row.employee_name])).appendTo(cell).on("change", event => {
					if (event.target.checked) selected.add(row.approval_name); else selected.delete(row.approval_name);
				});
			}
			const cells = hr ? [row.employee_name, `${row.week_start} - ${row.week_end}`, this.hours(row.total_hours)] : [row.employee_name, row.project_label || row.project, `${row.week_start} - ${row.week_end}`, this.hours(row.hours), __(row.project_status)];
			cells.forEach(value => $("<td></td>").text(value).appendTo(tr));
			this.button($("<td></td>").appendTo(tr), "Review entries", () => this.detail(row, hr));
		});
	}
	reports(reports) {
		reports.forEach(report => {
			const band = $('<section class="admin-reviews-section"></section>').appendTo(this.content);
			$("<h3></h3>").text(`${report.project} / ${report.week_start} - ${report.week_end}`).appendTo(band);
			const body = this.table(band, ["Employee", ...report.days, "Total", "Status", "Action"]);
			report.members.forEach(member => {
				const tr = $("<tr></tr>").appendTo(body);
				[member.employee_name, ...member.daily_hours.map(value => this.hours(value)), this.hours(member.weekly_total), __(member.status)].forEach(value => $("<td></td>").text(value).appendTo(tr));
				this.button($("<td></td>").appendTo(tr), "Review entries", () => this.detail({ ...member, project: report.project, week_start: report.week_start }, false));
			});
			this.button($('<div class="admin-reviews-toolbar"></div>').appendTo(band), "Approve project week", async () => {
				frappe.confirm(__("Approve all pending team members in this project week?"), async () => {
					await this.call("weekly_timesheet.approve_project_week", { project: report.project, week_start: report.week_start });
					await this.show();
				});
			}, true);
		});
	}
	async detail(row, hr) {
		const data = hr ? await this.call("weekly_timesheet.get_timesheet_review_detail", { name: row.name }) : await this.call("weekly_timesheet.get_project_review_detail", { project: row.project, week_start: row.week_start, employee: row.employee });
		const logs = hr ? data.time_logs : data.logs;
		const name = hr ? data.name : data.timesheet;
		const canReturn = hr ? data.docstatus === 0 && ["Draft", "Pending HR Review"].includes(data.custom_weekly_status) : data.can_return_entries;
		const dialog = new frappe.ui.Dialog({ title: `${data.employee_name} / ${hr ? data.custom_week_start : data.week_start}`, size: "extra-large", fields: [{ fieldname: "entries", fieldtype: "HTML" }] });
		const root = $('<div class="admin-reviews-detail"></div>').appendTo(dialog.fields_dict.entries.$wrapper);
		const selected = new Set();
		const body = this.table(root, ["", "Project", "Date", "Start", "End", "Hours", "Description", "Correction Reason", "Action"]);
		logs.forEach(log => {
			const tr = $("<tr></tr>").appendTo(body);
			const select = $("<td></td>").appendTo(tr);
			if (canReturn) $('<input type="checkbox">').attr("aria-label", __("Select time entry {0}", [log.name])).appendTo(select).on("change", event => {
				if (event.target.checked) selected.add(log.name); else selected.delete(log.name);
			});
			[log.project, log.date || String(log.from_time || "").slice(0, 10), hr ? String(log.from_time || "").slice(11, 16) : log.from_time, hr ? String(log.to_time || "").slice(11, 16) : log.to_time, this.hours(log.hours ?? log.duration), log.description || "", log.return_reason || ""].forEach(value => $("<td></td>").text(value).appendTo(tr));
			const cell = $("<td></td>").appendTo(tr);
			if (canReturn) this.button(cell, "Return entry", () => this.returnEntries(name, [log.name], hr, dialog));
		});
		const toolbar = $('<div class="admin-reviews-toolbar"></div>').appendTo(root);
		if (canReturn) this.button(toolbar, "Return selected entries", () => this.returnEntries(name, [...selected], hr, dialog));
		if (hr && data.custom_weekly_status === "Pending HR Review") {
			this.button(toolbar, "Return entire week", () => this.reason("Return entire week", async reason => {
				await this.call("weekly_timesheet.hr_return_weekly_timesheet", { name, reason });
				dialog.hide(); await this.show();
			}));
			this.button(toolbar, "Approve and close week", () => frappe.confirm(__("Approve and close this employee week?"), async () => {
				await this.call("weekly_timesheet.hr_close_weekly_timesheet", { name });
				dialog.hide(); await this.show();
			}), true);
		} else if (!hr && data.actionable) {
			this.button(toolbar, "Return entire project section", () => this.reason("Return entire project section", async reason => {
				await this.call("weekly_timesheet.review_project_approval", { approval_name: data.approval_name, action: "return", reason });
				dialog.hide(); await this.show();
			}));
			this.button(toolbar, "Approve project section", async () => {
				await this.call("weekly_timesheet.approve_project_review", { approval_name: data.approval_name });
				dialog.hide(); await this.show();
			}, true);
		}
		dialog.show();
	}
	reason(title, action) {
		frappe.prompt([{ fieldname: "reason", fieldtype: "Small Text", label: __("Correction Reason"), reqd: 1 }], values => action(values.reason), __(title));
	}
	returnEntries(name, entries, hr, dialog) {
		if (!entries.length) return frappe.msgprint(__("Select at least one time entry."));
		this.reason("Return selected entries", async reason => {
			await this.call("weekly_timesheet.return_timesheet_entries", { name, entries, reason, stage: hr ? "hr" : "project" });
			dialog.hide();
			frappe.show_alert({ message: __("Returned for correction"), indicator: "orange" });
			await this.show();
		});
	}
	hours(value) { return Number(value || 0).toFixed(2); }
}
