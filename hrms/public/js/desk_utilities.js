(() => {
	function simplify() {
		if (!frappe.boot?.hrms_admin_sidebar) return;
		document.body.classList.add("hrms-utilities-sidebar");
		const bottom = $(".body-sidebar-bottom");
		if (bottom.length && !bottom.find(".hrms-logout").length) {
			$('<button type="button" class="btn btn-default hrms-logout"></button>')
				.text(__("Log out")).prepend(frappe.utils.icon("log-out", "sm"))
				.appendTo(bottom).on("click", () => frappe.app.logout());
		}
	}
	$(document).on("toolbar_setup", simplify);
	$(simplify);
	frappe.router?.on("change", () => setTimeout(simplify, 0));
})();
