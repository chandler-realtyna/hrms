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
			const lookup = mode === "project-reports" ? "project-timesheets" : mode;
			const item = sections.flatMap(section => section.items).find(item => item.route === `/desk/admin-reviews/${lookup}`);
			if (!item) throw new Error(__("You do not have access to this review queue."));
			this.page.set_title(__(item.label));
			if (mode === "time-history") {
				await this.history(version);
				return;
			}
			if (["project-timesheets", "project-reports"].includes(mode)) {
				const views = $('<div class="admin-reviews-toolbar" role="tablist"></div>').appendTo(this.content);
				for (const [route, label] of [["project-timesheets", "Team entries"], ["project-reports", "Weekly review"]]) {
					this.button(views, label, () => frappe.set_route("admin-reviews", route), route === mode)
						.attr({ role: "tab", "aria-selected": String(route === mode) });
				}
			}
			if (mode === "project-timesheets") {
				const data = await this.call("weekly_timesheet.get_team_timesheet_sections", { view: this.teamView || "current", filters: this.teamFilters || {} });
				if (version === this.version) this.queue(data.rows, mode, data);
				return;
			}
			const methods = { "project-timesheets": "get_project_review_queue", "project-reports": "get_project_approval_queue", "hr-timesheets": "get_hr_weekly_timesheet_queue" };
			const rows = await this.call(`weekly_timesheet.${methods[mode]}`);
			if (version !== this.version) return;
			this.content.find(".admin-reviews-loading").remove();
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
	queue(rows, mode, paging = null) {
		const hr = mode === "hr-timesheets";
		let cursor = paging?.next_cursor, total = paging?.total;
		const selected = new Set();
		const toolbar = $('<div class="admin-reviews-toolbar"></div>').appendTo(this.content);
		if (paging) {
			for (const [view, label] of [["current", "Current"], ["history", "History"]])
				this.button(toolbar, label, () => { this.teamView = view; return this.show(); }, (this.teamView || "current") === view);
		}
		const search = $('<input type="search" class="form-control admin-reviews-search">').attr({ placeholder: __("Search employee, project or activity"), "aria-label": __("Search entries") }).appendTo(toolbar);
		const status = $('<select class="form-control admin-reviews-filter"></select>').attr("aria-label", __("Status")).appendTo(toolbar);
		$('<option value=""></option>').text(__("All statuses")).appendTo(status);
		(paging ? ["Draft", "Pending", "Returned", "Approved", "HR Review"] : [...new Set(rows.map(row => row.project_status).filter(Boolean))]).forEach(value => $('<option></option>').val(value).text(this.statusLabel(value)).appendTo(status));
		let approve;
		if (!hr && this.teamView !== "history") approve = this.button(toolbar, "Approve selected sections", async () => {
			if (!selected.size) return frappe.msgprint(__("Select pending sections first."));
			frappe.confirm(__("Approve {0} selected project sections?", [selected.size]), async () => {
				try { for (const approval_name of selected) await this.call("weekly_timesheet.approve_project_review", { approval_name }); }
				finally { await this.show(); }
			});
		}, true);
		if (approve) approve.prop("disabled", true);
		const counter = $('<div class="admin-reviews-count text-muted"></div>').appendTo(this.content);
		const body = this.table(this.content, hr ? ["Employee", "Week", "Hours", "Status", "Action"] : ["", "Employee", "Project", "Week", "Hours", "Activity Type", "Review", "Week status", "Updated", "Action"]);
		const render = () => {
			selected.clear(); if (approve) approve.prop("disabled", true); body.empty();
			const query = search.val().toLowerCase();
			const visible = rows.filter(row => (hr || !row.is_own_section)
				&& (!status.val() || row.project_status === status.val())
				&& (paging || [row.employee_name, row.project_label, ...(row.activity_types || [])].join(" ").toLowerCase().includes(query)))
				.sort((a, b) => String(b.modified || b.week_start).localeCompare(String(a.modified || a.week_start)));
			counter.text(paging ? __("{0} of {1} sections", [visible.length, total]) : __("{0} sections", [visible.length]));
		visible.forEach(row => {
			const tr = $("<tr></tr>").appendTo(body);
			if (!hr) {
				const cell = $("<td></td>").appendTo(tr);
				$('<input type="checkbox">').prop("disabled", !row.actionable).attr({ "aria-label": __("Select section for {0}", [row.employee_name]), title: __(row.selection_reason || (row.actionable ? "Select for approval" : "Only submitted sections awaiting project review can be approved")) }).appendTo(cell).on("change", event => {
					if (event.target.checked) selected.add(row.approval_name); else selected.delete(row.approval_name);
					approve?.prop("disabled", !selected.size);
				});
			}
			const cells = hr ? [row.employee_name, this.week(row.week_start, row.week_end), this.hours(row.total_hours)] : [row.employee_name, row.project_label || row.project, this.week(row.week_start, row.week_end), this.hours(row.hours), (row.activity_types || []).join(", ")];
			cells.forEach(value => $("<td></td>").text(value).appendTo(tr));
			if (!hr) this.statusCell($("<td></td>").appendTo(tr), row.project_status, row.routed_to_hr_reason);
			this.statusCell($("<td></td>").appendTo(tr), hr ? row.ready_for_hr_close ? "Pending HR Review" : "Pending Project Approval" : row.hr_status);
			if (!hr) $("<td></td>").text(row.modified ? moment(row.modified).format("D MMM HH:mm") : "").appendTo(tr);
			this.button($("<td></td>").appendTo(tr), "Review entries", () => this.detail(row, hr));
		});
		};
		if (paging) {
			search.val(this.teamFilters?.search || ""); status.val(this.teamFilters?.status || "");
			let request = 0, debounce;
			const more = this.button(this.content, "Load more", () => reload(false));
			const reload = async (reset = true) => {
				const version = ++request;
				const filters = this.teamFilters = { search: search.val(), status: status.val() };
				try {
					const page = await this.call("weekly_timesheet.get_team_timesheet_sections", {
						view: this.teamView || "current", cursor: reset ? null : cursor, filters,
					});
					if (version !== request) return;
					rows = reset ? page.rows : [...rows, ...page.rows];
					total = page.total; cursor = page.next_cursor;
					more.toggle(Boolean(cursor)); render();
				} catch (error) { frappe.msgprint(error.message || __("Could not load this page.")); }
			};
			search.on("input", () => { clearTimeout(debounce); debounce = setTimeout(reload, 300); });
			status.on("change", () => reload());
			more.toggle(Boolean(cursor));
		} else { search.on("input", render); status.on("change", render); }
		render();
	}
	reports(reports) {
		reports.forEach(report => {
			const band = $('<section class="admin-reviews-section"></section>').appendTo(this.content);
			$("<h3 class='admin-reviews-heading'></h3>").text(report.project_label || report.project).appendTo(band);
			$('<div class="text-muted admin-reviews-count"></div>').text(this.week(report.week_start, report.week_end)).appendTo(band);
			const body = this.table(band, ["Employee", "Activity Type", ...report.days.map(day => moment(day).format("ddd D")), "Hours", "Status", "Action"]);
			report.members.forEach(member => {
				const tr = $("<tr></tr>").appendTo(body);
				[member.employee_name, (member.activity_types || []).join(", ")].forEach(value => $("<td></td>").text(value).appendTo(tr));
				member.daily_hours.forEach(value => $('<td class="admin-reviews-number"></td>').toggleClass("text-muted", !Number(value)).text(Number(value) ? this.hours(value) : "-").appendTo(tr));
				$('<td class="admin-reviews-number font-weight-bold"></td>').text(this.hours(member.weekly_total)).appendTo(tr);
				this.statusCell($("<td></td>").appendTo(tr), member.status);
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
		const body = this.table(root, ["", "Project", "Date", "Start", "End", "Hours", "Activity Type", "Description", "Correction Reason", "Action"]);
		logs.forEach(log => {
			const tr = $("<tr></tr>").appendTo(body);
			const select = $("<td></td>").appendTo(tr);
			if (canReturn) $('<input type="checkbox">').attr("aria-label", __("Select time entry {0}", [log.name])).appendTo(select).on("change", event => {
				if (event.target.checked) selected.add(log.name); else selected.delete(log.name);
			});
			[row.project_label || log.project, this.date(log.date || String(log.from_time || "").slice(0, 10)), hr ? String(log.from_time || "").slice(11, 16) : log.from_time, hr ? String(log.to_time || "").slice(11, 16) : log.to_time, this.hours(log.hours ?? log.duration), log.activity_type || __("Unassigned"), log.description || "", log.return_reason || ""].forEach(value => $("<td></td>").text(value).appendTo(tr));
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
			if (data.ready_for_hr_close) this.button(toolbar, "Approve and close week", () => frappe.confirm(__("Approve and close this employee week?"), async () => {
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
	async history(version) {
		const filters = $('<div class="admin-history-filters"></div>').appendTo(this.content);
		const fields = new frappe.ui.FieldGroup({ body: filters, fields: [
			{ fieldname: "from_date", fieldtype: "Date", label: __("From Date"), reqd: 1 },
			{ fieldname: "to_date", fieldtype: "Date", label: __("To Date"), reqd: 1 },
			{ fieldname: "project", fieldtype: "Link", options: "Project", label: __("Project") },
			{ fieldname: "employee", fieldtype: "Link", options: "Employee", label: __("Employee") },
			{ fieldname: "activity_type", fieldtype: "Link", options: "Activity Type", label: __("Activity Type") },
			{ fieldname: "status", fieldtype: "Select", label: __("Week Status"), options: ["", "Draft", "Pending Project Approval", "Pending HR Review", "Correction Required", "Closed", "Submitted"] },
			{ fieldname: "group_by", fieldtype: "Select", label: __("Group By"), options: ["Project", "Employee", "Activity Type", "Month"], default: "Project" },
		] });
		fields.make();
		const toolbar = $('<div class="admin-reviews-toolbar"></div>').appendTo(this.content);
		const output = $('<div></div>').appendTo(this.content);
		let data;
		const load = async initial => {
			const values = initial ? {} : fields.get_values();
			if (!values) return;
			const group_by = { Project: "project", Employee: "employee", "Activity Type": "activity_type", Month: "month" }[values.group_by] || "project";
			output.empty().text(__("Loading"));
			exportButton.prop("disabled", true);
			try {
				const result = await this.call("management_reports.get_time_history", { ...values, group_by });
				if (version !== this.version) return;
				data = result;
				if (initial) { fields.set_value("from_date", data.from_date); fields.set_value("to_date", data.to_date); }
				output.empty();
				this.historyResults(output, data);
				exportButton.prop("disabled", !data.entries.length);
			} catch (error) {
				data = null;
				output.empty().append($('<div class="alert alert-danger"></div>').text(error.message || __("Could not load report")));
			}
		};
		this.button(toolbar, "Apply filters", () => load(false), true);
		const exportButton = this.button(toolbar, "Export CSV", () => {
			if (!data) return;
			const columns = ["Employee", "Project", "Activity Type", "Date", "Hours", "Week Status", "Timesheet"];
			const escape = value => `"${String(value ?? "").replace(/^(\s*[=+@\-]|[\t\r\n])/, "'$&").replace(/"/g, '""')}"`;
			const csv = [columns, ...data.entries.map(row => [row.employee_name, row.project_label, row.activity_type, String(row.from_time).slice(0, 10), row.hours, row.status, row.timesheet])].map(row => row.map(escape).join(",")).join("\r\n");
			const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
			const anchor = document.createElement("a"); anchor.href = url; anchor.download = `time-history-${data.from_date}-${data.to_date}.csv`;
			anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
		});
		await load(true);
	}
	historyResults(output, data) {
		const metrics = $('<dl class="admin-history-metrics"></dl>').appendTo(output);
		for (const [label, value] of [["Recorded hours", this.hours(data.totals.hours)], ["Closed hours", this.hours(data.totals.status_hours.Closed)], ["Time entries", data.totals.entries], ["Employees", data.totals.employees], ["Projects", data.totals.projects]]) {
			const metric = $('<div></div>').appendTo(metrics); $('<dt></dt>').text(__(label)).appendTo(metric); $('<dd></dd>').text(value).appendTo(metric);
		}
		if (!data.rows.length) { output.append($('<div class="admin-reviews-empty"></div>').text(__("No time entries in this period"))); return; }
		const states = ["Draft", "Pending Project Approval", "Pending HR Review", "Correction Required", "Closed", "Submitted"];
		const body = this.table(output, [__(data.group_by === "activity_type" ? "Activity Type" : data.group_by === "month" ? "Month" : data.group_by === "employee" ? "Employee" : "Project"), "Entries", "Recorded hours", ...states.map(status => this.statusLabel(status))]);
		const chart = $('<div class="admin-history-breakdown"></div>').appendTo(output);
		data.rows.forEach(row => {
			const tr = $('<tr></tr>').appendTo(body);
			this.button($('<td></td>').appendTo(tr), row.label, () => this.historyDetail(data, row));
			[row.entries, row.hours, ...states.map(state => row.status_hours[state] || 0)].forEach((value, index) => $('<td class="admin-reviews-number"></td>').toggleClass("text-muted", !value).text(index === 0 ? value : value ? this.hours(value) : "-").appendTo(tr));
		});
		const top = [...data.rows].sort((a, b) => b.hours - a.hours).slice(0, 10);
		top.forEach(row => {
			const line = $('<div class="admin-history-bar-row"></div>').appendTo(chart);
			$('<span></span>').text(row.label).appendTo(line);
			$('<progress></progress>').attr({ max: top[0].hours || 1, value: row.hours, "aria-label": row.label }).appendTo(line);
			$('<strong></strong>').text(this.hours(row.hours)).appendTo(line);
		});
	}
	historyDetail(data, group) {
		const entries = data.entries.filter(row => (data.group_by === "month" ? String(row.from_time).slice(0, 7) : row[data.group_by] || "Unassigned") === group.key);
		const dialog = new frappe.ui.Dialog({ title: group.label, size: "extra-large", fields: [{ fieldname: "entries", fieldtype: "HTML" }] });
		const root = $('<div></div>').appendTo(dialog.fields_dict.entries.$wrapper);
		const body = this.table(root, ["Employee", "Project", "Activity Type", "Date", "Hours", "Week Status", "Timesheet"]);
		let limit = 100;
		const render = () => {
			body.empty();
			entries.slice(0, limit).forEach(row => {
				const tr = $('<tr></tr>').appendTo(body);
				[row.employee_name, row.project_label, row.activity_type, this.date(String(row.from_time).slice(0, 10)), this.hours(row.hours)].forEach(value => $('<td></td>').text(value).appendTo(tr));
				this.statusCell($('<td></td>').appendTo(tr), row.status);
				$('<a></a>').attr('href', `/desk/timesheet/${encodeURIComponent(row.timesheet)}`).text(row.timesheet).appendTo($('<td></td>').appendTo(tr));
			});
			more.toggle(limit < entries.length);
		};
		const more = this.button(root, "Load more", () => { limit += 100; render(); });
		render(); dialog.show();
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
	statusLabel(status) {
		return __({ Draft: "Draft", Pending: "Pending", Returned: "Returned", Approved: "Approved", "HR Review": "HR", "Pending HR Review": "HR review", "Pending Project Approval": "Project review", "Correction Required": "Returned", Closed: "Final", Submitted: "Submitted" }[status] || status || "");
	}
	statusCell(cell, status, reason) {
		const color = ["Returned", "Correction Required"].includes(status) ? "orange" : ["Approved", "Closed"].includes(status) ? "green" : status === "Draft" ? "gray" : "blue";
		$('<span class="indicator-pill"></span>').addClass(color).text(this.statusLabel(status)).appendTo(cell);
		if (reason) $('<div class="text-muted small"></div>').text(__(reason === "self" ? "Own entries: final review by HR" : "No project lead: final review by HR")).appendTo(cell);
	}
	date(value) { return value ? moment(value).format("D MMM YYYY") : ""; }
	week(start, end) { return `${moment(start).format("D MMM")} - ${this.date(end)}`; }
	hours(value) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 }); }
}
