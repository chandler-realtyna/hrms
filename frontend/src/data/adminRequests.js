import { createResource } from "frappe-ui"

export const requests = createResource({
	url: "hrms.api.admin_desk.get_admin_review_requests",
	params: { limit: 200 },
	auto: true,
	transform(rows) {
		return rows
	},
})
