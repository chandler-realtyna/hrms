/* Native review lists retain their own query/permissions and existing status filters. */
(() => {
	const directCompany = new Set(["Leave Application", "Expense Claim", "Employee Invoice"]);
	const doctypes = [...directCompany, "Employee Holiday", "Employee Schedule"];
	for (const doctype of doctypes) {
		const settings = frappe.listview_settings[doctype] || {};
		if (settings.hr_company_filter) continue;
		settings.hr_company_filter = true;
		settings.add_fields = [...new Set([...(settings.add_fields || []), "employee", ...(directCompany.has(doctype) ? ["company"] : [])])];
		const previousOnload = settings.onload;
		const previousRefresh = settings.refresh;
		settings.onload = function (list) {
			if (previousOnload) previousOnload.call(this, list);
			return install(list, doctype);
		};
		settings.refresh = function (list) {
			if (previousRefresh) previousRefresh.call(this, list);
			groupPage(list);
		};
		frappe.listview_settings[doctype] = settings;
	}

	async function install(list, doctype) {
		if (list.hrCompanyInstalled) return;
		const roles = frappe.user_roles || [];
		if (frappe.session?.user !== "Administrator" && !roles.some(role => ["HR Manager", "HR User", "System Manager", "Company Desk Administrator"].includes(role))) return;
		list.hrCompanyInstalled = true;
		const response = await frappe.call({method: "hrms.api.review_company_filters.get_review_companies", args: {doctype}});
		const scope = response.message || {};
		list.hrCompanyScope = scope;
		const originalFilters = list.get_filters_for_args.bind(list);
		list.get_filters_for_args = function () {
			const filters = originalFilters();
			return list.hrCompanyFilter ? [...filters, list.hrCompanyFilter] : filters;
		};
		list.hrCompanyControl = list.page.add_field({
			fieldname: "hr_review_company", label: __("Company scope"), description: __("Existing list filters remain active."), fieldtype: "Select",
			options: [{label: __("All companies"), value: ""}, ...(scope.companies || []).map(name => ({label: name, value: name}))],
			default: "",
			change: async () => {
				const company = list.hrCompanyControl.get_value();
				const field = directCompany.has(doctype) ? "company" : "employee";
				// Extra AND condition; never clear route/status or manually entered filters.
				list.hrCompanyFilter = null;
				if (company) {
					const value = field === "company" ? company : Object.entries(scope.employee_companies || {}).filter(([, name]) => name === company).map(([employee]) => employee);
					list.hrCompanyFilter = [doctype, field, field === "company" ? "=" : "in", field === "company" ? value : (value.length ? value : ["__no_matching_employee__"])];
				}
				list.start = 0;
				list.refresh();
			},
		});
		// Page.add_field registers all controls as standard SQL filters. This UI-only
		// scope uses the valid company/employee condition above, never its own name.
		if (list.page.fields_dict?.hr_review_company === list.hrCompanyControl) {
			delete list.page.fields_dict.hr_review_company;
		}
		groupPage(list);
	}

	function groupPage(list) {
		if (!list.hrCompanyScope || !list.$result) return;
		list.$result.find(".hr-company-group").remove();
		const groups = new Map();
		for (const doc of list.data || []) {
			const company = doc.company || list.hrCompanyScope.employee_companies?.[doc.employee] || __("Company unavailable");
			const nameNode = list.$result.find("[data-name]").filter(function () {return $(this).attr("data-name") === doc.name;}).first();
			const row = nameNode.closest(".list-row-container");
			if (!row.length) continue;
			if (!groups.has(company)) groups.set(company, []);
			groups.get(company).push(row);
		}
		if (!groups.size) return;
		const anchor = $("<span></span>").insertBefore([...groups.values()][0][0]);
		for (const company of [...groups.keys()].sort((a, b) => a.localeCompare(b))) {
			const heading = $('<div class="hr-company-group text-muted" style="padding:12px 15px 6px;font-weight:600"></div>').text(`${company} · ${__("Loaded records")}`);
			heading.insertBefore(anchor);
			for (const row of groups.get(company)) row.insertBefore(anchor);
		}
		anchor.remove();
	}
})();
