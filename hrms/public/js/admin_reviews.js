frappe.pages["admin-reviews"].on_page_load = function (wrapper) {
	wrapper.admin_reviews = new HRMSAdminReviews(wrapper);
};
frappe.pages["admin-reviews"].on_page_show = function (wrapper) {
	wrapper.admin_reviews.show();
};

class HRMSAdminReviews {
	constructor(wrapper) {
		if (!document.getElementById("hrms-admin-reviews-style")) {
			$('<link id="hrms-admin-reviews-style" rel="stylesheet">')
				.attr("href", "/assets/hrms/css/admin_reviews.css?v=compact-review-summary-20261006").appendTo(document.head);
		}
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
		clearInterval(this.countsTimer);
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
			const companies = await this.call("management_reports.get_review_companies");
			if (version !== this.version) return;
			const companyFilter = $('<select class="form-control admin-reviews-filter"></select>').attr("aria-label", __("Company")).appendTo(this.content);
			$('<option value=""></option>').text(__("All companies")).appendTo(companyFilter);
			companies.forEach(company => $('<option></option>').val(company).text(company).appendTo(companyFilter));
			companyFilter.val(this.company || "").on("change", () => { this.company = companyFilter.val(); return this.show(); });

			if (mode === "time-history") {
				await this.history(version);
				return;
			}
			if (["project-timesheets", "project-reports"].includes(mode)) {
				const views = $('<div class="admin-reviews-toolbar" role="tablist"></div>').appendTo(this.content);
				for (const [route, label] of [["project-timesheets", "Project review follow-up"], ["project-reports", "Daily project summary"]]) {
					this.button(views, label, () => frappe.set_route("admin-reviews", route), route === mode)
						.attr({ role: "tab", "aria-selected": String(route === mode) });
				}
			}
			if (mode === "project-timesheets") {
				const data = await this.call("weekly_timesheet.get_team_timesheet_sections", { view: this.teamView || "current", filters: { review_scope: (frappe.session?.user === "Administrator" || (frappe.user_roles || []).some(role => ["HR Manager", "HR User", "System Manager", "Company Desk Administrator"].includes(role))) ? "submitted" : "all", ...(this.teamFilters || {}), company: this.company || "" } });
				if (version === this.version) { this.hrFollowup = data.can_hr_followup; this.queue(data.rows, mode, data); }
				return;
			}
			if (mode === "project-reports") {
				const week = $('<input type="date" class="form-control admin-reviews-filter">').attr("aria-label", __("Week containing date")).val(this.reportWeek || moment().format("YYYY-MM-DD")).appendTo(this.content);
				week.on("change", () => { this.reportWeek = week.val(); return this.show(); });
				const reports = await this.call("management_reports.get_daily_project_summary", {week_start: this.reportWeek || null, company: this.company || null});
				if (version === this.version) this.reports(reports);
				return;
			}
			const methods = { "project-timesheets": "get_project_review_queue", "project-reports": "get_project_approval_queue", "hr-timesheets": "get_hr_weekly_timesheet_queue" };
			const rows = await this.call(`weekly_timesheet.${methods[mode]}`, mode === "hr-timesheets" ? { view: this.hrView || "current", company: this.company || null } : {});
			if (version !== this.version) return;
			this.content.find(".admin-reviews-loading").remove();
			if (!rows.length && mode !== "hr-timesheets") this.content.append($('<div class="admin-reviews-empty"></div>').text(__("Nothing waiting for review")));
			else if (mode === "project-reports") this.reports(rows);
			else this.queue(rows, mode);
		} catch (error) {
			if (version === this.version) this.content.empty().append($('<div class="alert alert-danger"></div>').text(error.message || __("Could not load this review queue.")));
		}
	}
	home(sections) {
		this.homeBadges = new Map();
		sections.forEach(section => {
			const band = $('<section class="admin-reviews-section"></section>').appendTo(this.content);
			$("<h3 class='admin-reviews-heading'></h3>").text(__(section.label)).appendTo(band);
			const grid = $("<div class='admin-reviews-grid'></div>").appendTo(band);
			section.items.forEach(item => {
				const link = $("<a class='admin-reviews-link'></a>").attr({ href: item.route, "aria-label": __(item.label) }).appendTo(grid);
				$("<span class='admin-reviews-card-icon' aria-hidden='true'></span>").html(frappe.utils.icon(item.icon, "lg")).appendTo(link);
				$("<span class='admin-reviews-link-label'></span>").text(__(item.label)).appendTo(link);
				if (item.count_key) {
					const id = "hrms-review-count-" + item.count_key.toLowerCase().replace(/[^a-z0-9]+/g, "-");
					const badge = $("<span class='admin-reviews-count-badge'></span>").text("...")
						.attr({ id, title: __("Loading review count"), "aria-label": __("Loading review count") }).appendTo(link);
					link.attr("aria-describedby", id);
					this.homeBadges.set(item.count_key, { badge, label: item.label });
				}
				$("<span class='admin-reviews-link-icon' aria-hidden='true'></span>").html(frappe.utils.icon("right", "sm")).appendTo(link);
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
		this.updateHomeCounts(this.version);
		this.countsTimer = setInterval(() => {
			if (!document.hidden && frappe.get_route()[0] === "admin-reviews" && (frappe.get_route()[1] || "home") === "home") this.updateHomeCounts(this.version);
		}, 30000);
	}
	async updateHomeCounts(version) {
		const request = this.countRequest = (this.countRequest || 0) + 1;
		const badges = this.homeBadges;
		let counts;
		try { counts = await this.call("admin_desk.get_admin_desk_counts"); } catch { counts = {}; }
		if (version !== this.version || request !== this.countRequest) return;
		for (const [key, { badge, label }] of badges) {
			const count = counts[key], known = Number.isInteger(count) && count >= 0;
			const ready = counts["hr-timesheets-ready"];
			const capped = key === "hr-timesheets" && counts["hr-timesheets-capped"];
			const description = capped ? __("At least 500 submitted weeks. Ready count covers the latest 500 loaded weeks only.") : key === "hr-timesheets" ? __("Submitted weeks") : __("Awaiting review");
			badge.text(known ? (key === "hr-timesheets" && Number.isInteger(ready) ? __(capped ? "{0}+ weeks · {1} ready among loaded" : "{0} weeks · {1} ready", [count, ready]) : String(count)) : "-").toggleClass("is-empty", known && count === 0)
				.attr({ title: known ? description : __("Review count unavailable"),
					"aria-label": known ? (capped ? label + ": " + description : __("{0}: {1} items awaiting review", [label, count])) : __("Review count unavailable") });
		}
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
		if (hr) {
			for (const [view, label] of [["current", "Submitted weeks"], ["history", "Finalized weeks"]])
				this.button(toolbar, label, () => { this.hrView = view; return this.show(); }, (this.hrView || "current") === view);
		}
		if (paging) {
			for (const [view, label] of [["current", "Current"], ["history", "History"]])
				this.button(toolbar, label, () => { this.teamView = view; return this.show(); }, (this.teamView || "current") === view);
		}
		const search = $('<input type="search" class="form-control admin-reviews-search">').attr({ placeholder: __("Search employee, project or activity"), "aria-label": __("Search entries") }).appendTo(toolbar);
		const status = $('<select class="form-control admin-reviews-filter"></select>').attr("aria-label", __(hr ? "Week status" : "Status")).appendTo(toolbar);
		$('<option value=""></option>').text(__("All statuses")).appendTo(status);
		if (hr) {
			for (const [value, label] of [["Pending Project Approval", "Awaiting project approvals"], ["Correction Required", "Needs employee correction"], ["Pending HR Review", "Ready for HR review"], ["Closed", "Finalized"]])
				$('<option></option>').val(value).text(__(label)).appendTo(status);
		} else (paging ? ["Draft", "Pending", "Returned", "Approved", "HR Review"] : [...new Set(rows.map(row => row.project_status).filter(Boolean))]).forEach(value => $('<option></option>').val(value).text(this.statusLabel(value)).appendTo(status));
		let approve;
		if (!hr && this.teamView !== "history" && rows.some(row => row.regular_reviewer)) approve = this.button(toolbar, "Approve selected sections", async () => {
			if (!selected.size) return frappe.msgprint(__("Select pending sections first."));
			frappe.confirm(__("Approve {0} selected project sections?", [selected.size]), async () => {
				try { await this.call("weekly_timesheet.approve_project_reviews", { sections: rows.filter(row => selected.has(row.approval_name)).map(row => ({approval_name: row.approval_name, expected_modified: row.modified})) }); }
				finally { await this.show(); }
			});
		}, true);
		if (approve) approve.prop("disabled", true);

		const counter = $('<div class="admin-reviews-count text-muted"></div>').appendTo(this.content);
		if (hr && rows.length >= 500) $('<p class="text-muted small"></p>').text(__("Showing the latest 500 weeks. Older records are available in Time History.")).appendTo(this.content);
		const body = this.table(this.content, hr ? ["Employee", "Week", "Total time", "Week status", "Next action", "Action"] : ["", "Employee", "Project", "Week", "Total time", "Project review", "Next action", "Action"]);
		const render = () => {
			selected.clear(); if (approve) approve.prop("disabled", true); body.empty();
			const query = search.val().toLowerCase();
			const visible = rows.filter(row => (hr || !row.is_own_section)
				&& (!status.val() || (hr ? row.week_status === status.val() : row.project_status === status.val()))
				&& (paging || [row.employee_name, row.project_label, ...(row.project_labels || []), ...(row.activity_types || [])].join(" ").toLowerCase().includes(query)));
			if (!paging) visible.sort((a, b) => String(a.week_start || "").localeCompare(String(b.week_start || "")) || String(a.employee_name || "").localeCompare(String(b.employee_name || "")));
			counter.text(paging ? __("{0} of {1} sections", [visible.length, total]) : __(hr ? "{0} weeks" : "{0} sections", [visible.length]));
			const selectable = !hr && visible.some(row => row.actionable && row.regular_reviewer);
			if (!hr) body.closest("table").find("thead th").first().toggle(selectable);
			if (approve) approve.toggle(selectable);
		visible.sort((a, b) => String(a.company || "").localeCompare(String(b.company || "")));
		let company = Symbol();
		visible.forEach(row => {
			if (row.company !== company) {
				company = row.company;
				$('<th scope="rowgroup"></th>').attr("colspan", hr ? 6 : selectable ? 8 : 7).text(company || __("Company not specified")).appendTo($("<tr></tr>").appendTo(body));
			}
			const tr = $("<tr></tr>").appendTo(body);
			if (selectable) {
				const cell = $("<td></td>").appendTo(tr);
				if (row.actionable && row.regular_reviewer) $('<input type="checkbox">').attr({ "aria-label": __("Select section for {0}", [row.employee_name]), title: __("Select this saved section for approval") }).appendTo(cell).on("change", event => {
					if (event.target.checked) selected.add(row.approval_name); else selected.delete(row.approval_name);
					approve?.prop("disabled", !selected.size);
				});
			}
			const cells = hr ? [row.employee_name, this.week(row.week_start, row.week_end), this.hours(row.total_hours)] : [row.employee_name, row.project_label || row.project, this.week(row.week_start, row.week_end), this.duration(row.hours)];
			cells.forEach((value, index) => {
				const cell = $("<td></td>").appendTo(tr);
				if (index === 0) {
					const fallback = $('<span class="mr-2 text-muted"></span>').text(String(value || "?").slice(0, 1)).appendTo(cell);
					if (row.employee_image) $("<img>").attr({ src: row.employee_image, alt: "", width: 28, height: 28 }).css({ borderRadius: "50%", objectFit: "cover", marginRight: "8px" }).on("error", function () { $(this).remove(); fallback.show(); }).on("load", () => fallback.hide()).appendTo(cell);
				}
				cell.append(document.createTextNode(value || ""));
			});
			if (!hr) this.statusCell($("<td></td>").appendTo(tr), row.project_status, row.routed_to_hr_reason);
			if (hr) {
				this.statusCell($("<td></td>").appendTo(tr), row.week_status, null, true);
				$("<td></td>").text(row.week_status === "Closed" ? __("Finalized and locked") : row.ready_for_hr_close ? __("HR can finalize") : __("Follow up") + ": " + ((row.review_blockers || []).join("; ") || __("Awaiting review"))).appendTo(tr);
			}
			if (!hr) {
				const next = $("<td></td>").appendTo(tr);
				const reviewer = row.ping_reviewer_name || row.reviewer_name;
				const message = row.project_status === "Returned" ? __("Employee correction")
					: row.actionable && row.regular_reviewer ? __("Review saved entries")
					: row.actionable && row.hr_status === "Draft" ? __("In progress")
					: row.actionable ? reviewer || __("Project reviewer") : row.selection_reason || "";
				const primary = $('<div></div>').appendTo(next).text(message);
				const age = $('<div class="small admin-followup-age"></div>').appendTo(next);
				const updateAge = () => age.attr("title", (row.waiting_since ? __("Since {0}", [row.waiting_since]) : "") + (row.last_ping_at ? " · " + __("Last reminder: {0}", [moment(row.last_ping_at).format("D MMM HH:mm")]) : ""));
				if (row.waiting_days != null) age.addClass(row.waiting_days >= 7 ? "text-danger" : row.waiting_days >= 3 ? "text-warning" : "text-muted").text(__("Waiting {0} days", [row.waiting_days]));
				updateAge();
				if (row.can_ping) this.button(primary, "Remind", () => frappe.confirm(__("Send an in-app reminder to {0} to review {1}’s week {2}?", [reviewer || __("the current project reviewer"), row.employee_name, this.week(row.week_start, row.week_end)]), async () => {
					const result = await this.call("project_review_followup.ping_project_reviewer", {name: row.timesheet, project: row.project, expected_modified: row.modified, expected_reviewer: row.ping_reviewer});
					frappe.show_alert({message: result.message, indicator: result.sent ? "green" : "orange"});
					row.last_ping_at = result.last_ping_at; updateAge();
				})).addClass("ml-2");
			}
			this.button($("<td></td>").appendTo(tr), "Review entries", () => this.detail(row, hr));
		});
		};
		if (paging) {
			search.val(this.teamFilters?.search || ""); status.val(this.teamFilters?.status || "");
			const scope = $('<select class="form-control admin-reviews-filter"></select>').attr("aria-label", __("Follow-up scope")).appendTo(toolbar);
			for (const [value, label] of [["submitted", "Submitted weeks"], ["draft", "In-progress weeks"], ["all", "All saved sections"]]) $('<option></option>').val(value).text(__(label)).appendTo(scope);
			scope.val(this.teamFilters?.review_scope || (this.hrFollowup ? "submitted" : "all"));
			const week = $('<input type="date" class="form-control admin-reviews-filter">').attr({"aria-label": __("Week containing date"), title: __("Blank means all weeks. Any date selects its Sunday–Saturday week.")}).val(this.teamFilters?.week_start || "").appendTo(toolbar);
			$('<span class="text-muted small"></span>').text(__("Week filter · blank means all weeks")).appendTo(toolbar);
			let request = 0, debounce;
			const more = this.button(this.content, "Load more", () => reload(false));
			const reload = async (reset = true) => {
				const version = ++request;
				const filters = this.teamFilters = { search: search.val(), status: status.val(), company: this.company || "", review_scope: scope.val(), week_start: week.val() };
				try {
					const page = await this.call("weekly_timesheet.get_team_timesheet_sections", {
						view: this.teamView || "current", cursor: reset ? null : cursor, filters,
					});
					if (version !== request) return;
					rows = reset ? page.rows : [...rows, ...page.rows];
					total = page.total; cursor = page.next_cursor;
					more.toggle(Boolean(cursor)); render();
				} catch (error) {
					if (version !== request) return;
					if (!reset && (error.exc_type || error.responseJSON?.exc_type) === "TeamCursorResetRequired") {
						cursor = null;
						frappe.show_alert({ message: __("List updated. Showing the first page."), indicator: "blue" });
						return reload(true);
					}
					frappe.msgprint(error.message || __("Could not load this page."));
				}
			};
			search.on("input", () => { clearTimeout(debounce); debounce = setTimeout(reload, 300); });
			status.on("change", () => reload());
			scope.on("change", () => reload());
			week.on("change", () => reload());
			more.toggle(Boolean(cursor));
		} else { search.on("input", render); status.on("change", render); }
		render();
		if (hr) {
			const guide = $('<details class="admin-review-guide"></details>').appendTo(this.content);
			$('<summary></summary>').text(__("Workflow guide")).appendTo(guide);
			$('<p class="text-muted small"></p>').text(__("Employees save and review their time, then submit their week. Project leads review only their project sections; their own entries and sections without an independent project lead go to HR. Follow up with the listed reviewer for pending project approvals, or with the employee for corrections. HR finalizes only a submitted week whose own required project reviews are complete. Other employees’ reviews do not block this week. Finalized weeks are locked and appear in history. Submission deadlines and scheduled reminders are not configured yet; contact HR for late submissions or corrections.")).appendTo(guide);
		}
	}
	reports(reports) {
		const toolbar = $('<div class="admin-summary-toolbar"></div>').prependTo(this.content);
		const company = this.content.children('select.admin-reviews-filter').first().detach();
		const date = this.content.children('input[type="date"]').first().detach();
		for (const [control, label] of [[company, "Company"], [date, "Week containing date"]]) {
			if (!control.length) continue;
			const field = $('<label class="admin-summary-filter"></label>').appendTo(toolbar);
			$('<span class="text-muted small"></span>').text(__(label)).appendTo(field);
			control.appendTo(field);
		}
		const searchField = $('<label class="admin-summary-filter admin-summary-search"></label>').appendTo(toolbar);
		$('<span class="text-muted small"></span>').text(__("Search projects or employees")).appendTo(searchField);
		const search = $('<input type="search" class="form-control">').attr({placeholder:__("Project, employee or activity"), "aria-label":__("Search project summaries")}).appendTo(searchField);
		const start = reports[0]?.week_start || moment(this.reportWeek || undefined).day(0).format("YYYY-MM-DD");
		const end = reports[0]?.week_end || moment(start).add(6, "days").format("YYYY-MM-DD");
		const recorded = reports.filter(report => report.members.length);
		const total = reports.reduce((sum, report) => sum + report.members.reduce((hours, member) => hours + Number(member.weekly_total || 0), 0), 0);
		const overview = $('<div class="admin-summary-overview"></div>').appendTo(this.content);
		$('<strong></strong>').text(this.week(start, end)).appendTo(overview);
		$('<span class="text-muted"></span>').text(__("{0} projects · {1} with recorded time · {2} recorded", [reports.length, recorded.length, this.duration(total)])).appendTo(overview);
		$('<p class="text-muted small admin-summary-purpose"></p>').text(__("Recorded time by project and day. Project review and final HR approval are separate steps.")).appendTo(this.content);
		const groups = new Map();
		reports.forEach(report => {
			const key = report.company || __("Company not specified");
			if (!groups.has(key)) groups.set(key, []);
			groups.get(key).push(report);
		});
		const rendered = [];
		const drawProject = (report, target) => {
			const band = $('<details class="admin-project-summary"></details>').appendTo(target);
			const heading = $('<summary class="admin-summary-project-heading"></summary>').appendTo(band);
			$('<span class="admin-summary-project-name"></span>').text(report.project_label || report.project).appendTo(heading);
			const hours = report.members.reduce((sum, member) => sum + Number(member.weekly_total || 0), 0);
			const count = new Set(report.members.map(member => member.employee || member.employee_name)).size;
			$('<span class="admin-summary-project-metrics"></span>').text(report.members.length ? __(count === 1 ? "{0} · {1} employee" : "{0} · {1} employees", [this.duration(hours), count]) : __("No recorded time")).appendTo(heading);
			let drawn = false;
			band.on("toggle", () => {
				if (!band.prop("open") || drawn) return;
				drawn = true;
				if (!report.members.length) {
					$('<p class="text-muted small admin-summary-no-time"></p>').text(__("No time recorded for this week")).appendTo(band);
					return;
				}
				const body = this.table(band, ["Employee", "Activity Type", ...report.days.map(day => moment(day).format("ddd D")), "Total time", "Project review", "Details"]);
				report.members.forEach(member => {
					const tr = $("<tr></tr>").appendTo(body);
					const employee = $('<td></td>').appendTo(tr);
					const identity = $('<span class="admin-summary-employee"></span>').appendTo(employee);
					const fallback = $('<span class="admin-summary-avatar" aria-hidden="true"></span>').text(String(member.employee_name || "?").slice(0, 1)).appendTo(identity);
					if (member.employee_image) $('<img class="admin-summary-avatar">').attr({src:member.employee_image, alt:"", width:24, height:24}).on("error", function(){ $(this).remove(); fallback.show(); }).on("load", () => fallback.hide()).appendTo(identity);
					$('<span></span>').text(member.employee_name).appendTo(identity);
					$('<td></td>').text((member.activity_types || []).filter(value => value && value !== "Unassigned").join(", ")).appendTo(tr);
					member.daily_hours.forEach(value => $('<td class="admin-reviews-number"></td>').toggleClass("text-muted", !Number(value)).text(Number(value) ? this.duration(value) : "-").appendTo(tr));
					$('<td class="admin-reviews-number font-weight-bold"></td>').text(this.duration(member.weekly_total)).appendTo(tr);
					this.statusCell($("<td></td>").appendTo(tr), member.status);
					const action = $("<td></td>").appendTo(tr);
					if (member.includes_legacy_entries) $('<span class="text-muted small"></span>').text(__("Includes legacy daily records · details in Time History")).appendTo(action);
					else this.button(action, "View entries", () => this.detail({ ...member, project: report.project, week_start: report.week_start }, false));
				});
				const totals = $('<tr class="admin-summary-total-row"></tr>').appendTo(body);
				$('<th scope="row" colspan="2"></th>').text(__("Project total")).appendTo(totals);
				report.days.forEach((day, index) => {
					const hours = report.members.reduce((sum, member) => sum + Number(member.daily_hours[index] || 0), 0);
					$('<td class="admin-reviews-number"></td>').text(hours ? this.duration(hours) : "-").appendTo(totals);
				});
				$('<td class="admin-reviews-number font-weight-bold"></td>').text(this.duration(hours)).appendTo(totals);
				$('<td colspan="2"></td>').appendTo(totals);
			});
			return {band, searchText:[report.company, report.project_label, report.project, ...report.members.flatMap(member => [member.employee_name, ...(member.activity_types || [])])].join(" ").toLowerCase()};
		};
		[...groups].sort(([a], [b]) => a.localeCompare(b)).forEach(([name, projects]) => {
			const group = $('<section class="admin-summary-company"></section>').appendTo(this.content);
			$('<h3 class="admin-reviews-heading"></h3>').text(name).appendTo(group);
			const active = projects.filter(report => report.members.length).sort((a,b) => String(a.project_label || a.project).localeCompare(String(b.project_label || b.project)));
			const empty = projects.filter(report => !report.members.length).sort((a,b) => String(a.project_label || a.project).localeCompare(String(b.project_label || b.project)));
			const activeRows = active.map(report => drawProject(report, group));
			let emptyGroup, emptyTitle, emptyRows = [];
			if (empty.length) {
				emptyGroup = $('<details class="admin-summary-empty-projects"></details>').appendTo(group);
				emptyTitle = $('<summary></summary>').text(__("Projects without recorded time ({0})", [empty.length])).appendTo(emptyGroup);
				emptyRows = empty.map(report => drawProject(report, emptyGroup));
			}
			rendered.push({group, activeRows, emptyGroup, emptyTitle, emptyRows});
		});
		const noMatch = $('<p class="admin-reviews-empty" role="status"></p>').text(__("No projects match your search")).hide().appendTo(this.content);
		let searching = false;
		search.on("input", () => {
			const query = String(search.val()).trim().toLowerCase();
			let count = 0;
			rendered.forEach(group => {
				const apply = rows => rows.filter(row => { const match = row.searchText.includes(query); row.band.toggle(match); return match; }).length;
				const active = apply(group.activeRows), empty = apply(group.emptyRows);
				group.group.toggle(Boolean(active + empty)); count += active + empty;
				if (group.emptyGroup) {
					if (query && !searching) group.wasOpen = group.emptyGroup.prop("open");
					group.emptyGroup.toggle(Boolean(empty)).prop("open", query ? Boolean(empty) : searching ? Boolean(group.wasOpen) : group.emptyGroup.prop("open"));
					group.emptyTitle.text(__("Projects without recorded time ({0})", [empty]));
				}
			});
			searching = Boolean(query);
			noMatch.toggle(!count);
		});
		if (!reports.length) noMatch.text(__("No projects available for this company")).show();
	}
	async detail(row, hr) {
		const data = hr ? await this.call("weekly_timesheet.get_timesheet_review_detail", { name: row.name }) : await this.call("weekly_timesheet.get_project_review_detail", { project: row.project, week_start: row.week_start, employee: row.employee });
		const logs = hr ? data.time_logs : data.logs;
		const name = hr ? data.name : data.timesheet;
		const canReturn = hr ? data.docstatus === 0 && ["Draft", "Pending HR Review"].includes(data.custom_weekly_status) : data.can_return_entries && data.regular_reviewer;
		const dialog = new frappe.ui.Dialog({ title: `${data.employee_name} / ${this.week(hr ? data.custom_week_start : data.week_start, hr ? data.custom_week_end : data.week_end)}`, size: "extra-large", fields: [{ fieldname: "entries", fieldtype: "HTML" }] });
		const root = $('<div class="admin-reviews-detail"></div>').appendTo(dialog.fields_dict.entries.$wrapper);
		if (!hr) {
			const summary = $('<div class="admin-reviews-toolbar"></div>').appendTo(root);
			for (const [label, value] of [["This project section", data.project_status], ["Employee week", data.hr_status]]) {
				const item = $('<div></div>').appendTo(summary);
				$('<span></span>').text(__(label) + ": ").appendTo(item);
				this.statusCell(item, value, null, label === "Employee week");
			}
		}
		if (hr) {
			const state = data.custom_weekly_status;
			const color = state === "Closed" || data.ready_for_hr_close ? "green" : state === "Correction Required" ? "red" : "amber";
			const card = $('<div class="admin-review-action-card"></div>').attr("data-state", color).appendTo(root);
			$('<strong></strong>').text(this.weekStatusLabel(state)).appendTo(card);
			const next = state === "Closed" ? "Finalized and locked. View this week in history." : data.ready_for_hr_close ? "Your next action: check the entries and finalize this week." : state === "Correction Required" ? "Next action: the employee must correct and resubmit." : "Your next action: follow up with the project reviewers.";
			$('<p></p>').text(__(next)).appendTo(card);
			if (!data.ready_for_hr_close && state !== "Closed") {
				for (const blocker of data.review_blockers || []) $('<div class="small"></div>').text(blocker).appendTo(card);
				if (state === "Pending Project Approval") $('<a class="btn btn-warning btn-sm mt-2"></a>').attr("href", "/desk/admin-reviews/project-timesheets").text(__("View project reviews")).appendTo(card);
			}
		}

		const approvalNote = data.custom_weekly_status === "Closed" || data.hr_status === "Closed"
			? "Finalized by HR. This week is locked."
			: hr ? data.ready_for_hr_close
				? "Project reviews complete. HR approval is still required."
				: data.custom_weekly_status === "Correction Required" ? "The employee must correct and resubmit this week before HR can finalize it." : "Follow up with the project reviewers listed below for this employee’s own entries. Reviews of other employees’ entries are separate tasks and do not delay this week’s final HR approval."
			: "Project approval does not finalize the week. Final approval is by HR.";
		const guide = $('<details class="admin-review-guide"></details>').appendTo(root);
		$('<summary></summary>').text(__("Workflow guide")).appendTo(guide);
		$('<p class="text-muted small"></p>').text(__(approvalNote)).appendTo(guide);
		const selected = new Set();
		const toolbar = $('<div class="admin-reviews-toolbar"></div>').appendTo(root);
		if (hr) {
			const totals = $('<div class="admin-reviews-count"></div>').appendTo(toolbar);
			$('<strong></strong>').text(__("Recorded time") + ": " + this.duration(logs.reduce((sum, log) => sum + Number(log.hours ?? log.duration ?? 0), 0))).appendTo(totals);
			$('<span></span>').text(" · " + __("Expected work time") + ": " + (data.expected_work?.hours == null ? __("Not available") : this.duration(data.expected_work.hours))).attr("title", data.expected_work?.reason || "").appendTo(totals);
		}
		let secondaryActions = toolbar;
		let secondaryMenu;
		if (hr && (canReturn || (data.docstatus === 0 && ["Pending Project Approval", "Pending HR Review", "Correction Required"].includes(data.custom_weekly_status)))) {
			secondaryMenu = $('<details class="position-relative"></details>').appendTo(toolbar);
			$('<summary class="btn btn-default btn-sm"></summary>').attr({"aria-label": __("More actions"), title: __("More actions")}).text("⋯").appendTo(secondaryMenu);
			secondaryActions = $('<div class="dropdown-menu show"></div>').css({position:"absolute", minWidth:"220px", zIndex:1055, padding:"8px", display:"flex", flexDirection:"column", gap:"6px"}).appendTo(secondaryMenu);
			secondaryActions.on("click", "button", () => secondaryMenu.prop("open", false));
		}
		if (hr && data.docstatus === 0 && ["Pending Project Approval", "Pending HR Review", "Correction Required"].includes(data.custom_weekly_status)) {
			this.button(secondaryActions, "Reopen week for editing", () => this.reason("Reopen week for editing", async reason => {
				await this.call("weekly_timesheet.reopen_weekly_timesheet", { name, expected_modified: data.modified, reason });
				dialog.hide(); await this.show();
			}));
		}

		const sourceZone = data.source_timezone || frappe.boot.time_zone?.system || "UTC";
		let displayZone = moment.tz ? (Intl.DateTimeFormat().resolvedOptions().timeZone || frappe.boot.time_zone?.user || sourceZone) : sourceZone;
		const zoneLabel = $("<label></label>").text(__("Time zone") + " ").appendTo(root);
		const zone = $('<select class="form-control input-sm"></select>').attr("aria-label", __("Time zone")).appendTo(zoneLabel);
		for (const name of [...new Set([displayZone, sourceZone, "UTC", Intl.DateTimeFormat().resolvedOptions().timeZone])]) $("<option></option>").val(name).text(name).appendTo(zone);
		zone.val(displayZone).prop("disabled", !moment.tz);
		const timeCells = [];
		const updateTimes = () => timeCells.forEach(({ cell, value, dateOnly }) => cell.text(value ? (moment.tz ? moment.tz(value, sourceZone).tz(displayZone).format(dateOnly ? "D MMM YYYY" : "D MMM YYYY HH:mm") : dateOnly ? this.date(String(value).slice(0, 10)) : value) : ""));
		zone.on("change", () => { displayZone = zone.val(); updateTimes(); });
		const showCorrectionReason = logs.some(log => Boolean(log.return_reason));
		const body = this.table(root, ["", "Project", "Date", "Start", "End", "Time", "Activity Type", "Description", ...(showCorrectionReason ? ["Correction Reason"] : []), "Action"]);
		logs.forEach(log => {
			const tr = $("<tr></tr>").appendTo(body);
			const select = $("<td></td>").appendTo(tr);
			if (canReturn) $('<input type="checkbox">').attr("aria-label", __("Select time entry {0}", [log.name])).appendTo(select).on("change", event => {
				if (event.target.checked) selected.add(log.name); else selected.delete(log.name);
			});
			[log.project_label || row.project_label || log.project, this.date(log.date || String(log.from_time || "").slice(0, 10)), hr ? String(log.from_time || "").slice(11, 16) : log.from_time, hr ? String(log.to_time || "").slice(11, 16) : log.to_time, this.entryHours(log.hours ?? log.duration), log.activity_type && log.activity_type !== "Unassigned" ? log.activity_type : "", log.description || "", ...(showCorrectionReason ? [log.return_reason || ""] : [])].forEach((value, index) => { const cell = $("<td></td>").text(value).appendTo(tr); if ([1, 2, 3].includes(index)) timeCells.push({ cell, value: index === 3 ? (log.to_datetime || log.to_time) : (log.from_datetime || log.from_time), dateOnly: index === 1 }); });
			const cell = $("<td></td>").appendTo(tr);
			if (canReturn) this.button(cell, "Return entry", () => this.returnEntries(name, [log.name], hr, dialog));
		});
		updateTimes();
		if (canReturn) this.button(secondaryActions, "Return selected entries", () => this.returnEntries(name, [...selected], hr, dialog));
		if (hr && data.custom_weekly_status === "Pending HR Review") {
			this.button(secondaryActions, "Return entire week", () => this.reason("Return entire week", async reason => {
				await this.call("weekly_timesheet.hr_return_weekly_timesheet", { name, reason });
				dialog.hide(); await this.show();
			}));
			if (data.ready_for_hr_close) this.button(toolbar, "Finalize week", () => frappe.confirm(__("Give final HR approval? This locks the entire week and moves it to history. The contractor will be notified."), async () => {
				await this.call("weekly_timesheet.hr_close_weekly_timesheet", { name });
				frappe.show_alert({ message: __("Week finalized. Locked and moved to history."), indicator: "green" });
				dialog.hide(); await this.show();
			}), true);
		} else if (!hr && data.actionable && data.regular_reviewer) {
			this.button(toolbar, "Return entire project section", () => this.reason("Return entire project section", async reason => {
				await this.call("weekly_timesheet.review_saved_project_entries", { name, project: data.project, expected_modified: data.modified, action: "return", reason });
				dialog.hide(); await this.show();
			}));
			this.button(toolbar, "Approve project section", async () => {
				await this.call("weekly_timesheet.review_saved_project_entries", { name, project: data.project, expected_modified: data.modified });
				dialog.hide(); await this.show();
			}, true);
		}
		if (!hr && data.hr_exception) {
			const menu = $('<details class="admin-review-guide"></details>').appendTo(toolbar);
			$('<summary class="btn btn-default btn-sm"></summary>').text(__("Exceptional HR actions")).appendTo(menu);
			$('<p class="text-muted small"></p>').text(__("Use only when the project reviewer cannot act. A reason is recorded in the review history.")).appendTo(menu);
			const intervene = (label, action) => this.button(menu, label, () => this.reason(label, async reason => {
				await this.call("weekly_timesheet.review_saved_project_entries", {name, project:data.project, expected_modified:data.modified, action, reason});
				dialog.hide(); await this.show();
			}));
			if (data.actionable) intervene("Approve on behalf of project reviewer", "approve");
			if (data.can_return_entries) intervene("Return project section for employee correction", "return");
			if (data.can_reset_review) this.button(menu, "Revoke approval and request project review", () => this.reason("Revoke approval and request project review", async reason => {
				await this.call("weekly_timesheet.reset_project_review", {name, project:data.project, expected_modified:data.modified, reason});
				dialog.hide(); await this.show();
			}));
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
		fields.fields_dict.status.$input.find("option").each((index, option) => {
			if (option.value) $(option).text(this.weekStatusLabel(option.value));
		});
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
				const result = await this.call("management_reports.get_time_history", { ...values, group_by, company: this.company || null });
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
			const columns = ["Employee", "Project", "Activity Type", "Date", "Hours", "Week Status", "Timesheet"].map(label => __(label));
			const escape = value => `"${String(value ?? "").replace(/^(\s*[=+@\-]|[\t\r\n])/, "'$&").replace(/"/g, '""')}"`;
			const csv = [columns, ...data.entries.map(row => [row.employee_name, row.project_label, row.activity_type, String(row.from_time).slice(0, 10), row.hours, this.weekStatusLabel(row.status), row.timesheet])].map(row => row.map(escape).join(",")).join("\r\n");
			const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
			const anchor = document.createElement("a"); anchor.href = url; anchor.download = `time-history-${data.from_date}-${data.to_date}.csv`;
			anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
		});
		await load(true);
	}
	historyResults(output, data) {
		const metrics = $('<dl class="admin-history-metrics"></dl>').appendTo(output);
		for (const [label, value] of [["Recorded hours", this.hours(data.totals.hours)], ["Finalized hours", this.hours(data.totals.status_hours.Closed)], ["Time entries", data.totals.entries], ["Employees", data.totals.employees], ["Projects", data.totals.projects]]) {
			const metric = $('<div></div>').appendTo(metrics); $('<dt></dt>').text(__(label)).appendTo(metric); $('<dd></dd>').text(value).appendTo(metric);
		}
		if (!data.rows.length) { output.append($('<div class="admin-reviews-empty"></div>').text(__("No time entries in this period"))); return; }
		const states = ["Draft", "Pending Project Approval", "Pending HR Review", "Correction Required", "Closed", "Submitted"];
		$('<h3 class="admin-reviews-heading"></h3>').text(__("Hours by week status")).appendTo(output);
		$('<p class="text-muted small"></p>').text(__("These are whole-week stages, not individual project approvals. Only Finalized means final HR approval.")).appendTo(output);
		if (data.totals.status_hours.Submitted) $('<p class="text-muted small"></p>').text(__("Legacy submitted: submitted outside the weekly HR approval workflow.")).appendTo(output);
		const body = this.table(output, [__(data.group_by === "activity_type" ? "Activity Type" : data.group_by === "month" ? "Month" : data.group_by === "employee" ? "Employee" : "Project"), "Entries", "Recorded hours", ...states.map(status => this.weekStatusLabel(status))]);
		const chart = $('<div class="admin-history-breakdown"></div>').appendTo(output);
		let company = Symbol();
		data.rows.forEach(row => {
			if (row.company !== company) { company = row.company; $('<th scope="rowgroup"></th>').attr("colspan", 3 + states.length).text(company || __("Company not specified")).appendTo($("<tr></tr>").appendTo(body)); }
			const tr = $('<tr></tr>').appendTo(body);
			this.button($('<td></td>').appendTo(tr), row.label, () => this.historyDetail(data, row)).removeClass("btn-default").addClass("admin-history-group");
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
		const entries = data.entries.filter(row => row.company === group.company && (data.group_by === "month" ? String(row.from_time).slice(0, 7) : row[data.group_by] || "Unassigned") === group.key);
		const dialog = new frappe.ui.Dialog({ title: group.label, size: "extra-large", fields: [{ fieldname: "entries", fieldtype: "HTML" }] });
		const root = $('<div></div>').appendTo(dialog.fields_dict.entries.$wrapper);
		const body = this.table(root, ["Employee", "Project", "Activity Type", "Date", "Hours", "Week Status", "Timesheet"]);
		let limit = 100;
		const render = () => {
			body.empty();
			entries.slice(0, limit).forEach(row => {
				const tr = $('<tr></tr>').appendTo(body);
				[row.employee_name, row.project_label, row.activity_type, this.date(String(row.from_time).slice(0, 10)), this.hours(row.hours)].forEach(value => $('<td></td>').text(value).appendTo(tr));
				this.statusCell($('<td></td>').appendTo(tr), row.status, null, true);
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
		return __({ Draft: "Not reviewed", Pending: "Awaiting project review", Returned: "Needs correction", Approved: "Project approved", "HR Review": "HR review required", "Pending HR Review": "HR review", "Pending Project Approval": "Project review", "Correction Required": "Returned", Closed: "Final", Submitted: "Submitted" }[status] || status || "");
	}
	weekStatusLabel(status) {
		return __({ Draft: "Not submitted", "Pending Project Approval": "Awaiting project review", "Pending HR Review": "Ready for HR review", "Correction Required": "Needs employee correction", Closed: "Finalized", Submitted: "Legacy submitted" }[status] || status || "");
	}
	statusCell(cell, status, reason, week = false) {
		cell.addClass(week ? "admin-reviews-week-status" : "admin-reviews-project-status");
		const color = status === "Correction Required" || status === "Returned" ? "red" : week && status === "Pending Project Approval" ? "orange" : week && status === "Pending HR Review" ? "green" : ["Approved", "Closed"].includes(status) ? "green" : status === "Draft" ? "gray" : "blue";
		$('<span class="indicator-pill"></span>').addClass(color).text(week ? this.weekStatusLabel(status) : this.statusLabel(status)).appendTo(cell);
		if (reason) $('<div class="text-muted small"></div>').text(__(reason === "self" ? "Own entries: final review by HR" : "No project lead: final review by HR")).appendTo(cell);
	}
	date(value) { return value ? moment(value).format("D MMM YYYY") : ""; }
	week(start, end) { return `${moment(start).format("D MMM")} - ${this.date(end)}`; }
	entryHours(value) { return this.duration(value); }
	duration(value) {
		const hours = Number(value || 0);
		if (hours > 0 && hours < 1 / 60) return __("Under 1 minute");
		const minutes = Math.round(hours * 60);
		const wholeHours = Math.floor(minutes / 60), remainingMinutes = minutes % 60;
		return wholeHours ? `${wholeHours}h${remainingMinutes ? ` ${remainingMinutes}m` : ""}` : `${remainingMinutes}m`;
	}
	hours(value) { return this.duration(value); }
}
