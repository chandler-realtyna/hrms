const setupSelfProfileRoute = () => {
	if (!frappe.ui?.toolbar?.route_to_user || frappe.user.has_role("System Manager")) {
		return;
	}

	frappe.ui.toolbar.route_to_user = () => {
		window.location.assign(`/update-profile/${encodeURIComponent(frappe.session.user)}/edit`);
		return false;
	};
};

$(document).on("toolbar_setup", setupSelfProfileRoute);
setupSelfProfileRoute();
