frappe.pages["admin-reviews"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Admin Reviews"),
		single_column: true,
	});
	const content = $('<div class="admin-reviews-page"></div>').appendTo(page.main);
	content.append(`<div class="admin-reviews-loading"><span class="spinner-border spinner-border-sm"></span> ${__("Loading")}</div>`);

	frappe.call({
		method: "hrms.api.admin_desk.get_admin_desk_sections",
		callback(response) {
			const sections = response.message || [];
			content.empty();
			if (!sections.length) {
				frappe.set_route("desktop");
				return;
			}

			sections.forEach((section) => {
				const sectionEl = $("<section class='admin-reviews-section'></section>");
				$("<h3 class='admin-reviews-heading'></h3>").text(__(section.label)).appendTo(sectionEl);
				const grid = $("<div class='admin-reviews-grid'></div>").appendTo(sectionEl);
				section.items.forEach((item) => {
					const link = $("<a class='admin-reviews-link'></a>").attr("href", item.route);
					$("<span class='admin-reviews-link-label'></span>").text(__(item.label)).appendTo(link);
					$("<span class='admin-reviews-link-icon'>&gt;</span>").attr("aria-hidden", "true").appendTo(link);
					link.appendTo(grid);
				});
				content.append(sectionEl);
			});
		},
		error() {
			content.empty().append($(`<div class="alert alert-danger">${__("Could not load your available workspaces.")}</div>`));
		},
	});
};
