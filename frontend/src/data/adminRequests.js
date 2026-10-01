import { markRaw } from "vue"
import { createResource } from "frappe-ui"

import LeaveRequestItem from "@/components/LeaveRequestItem.vue"
import ExpenseClaimItem from "@/components/ExpenseClaimItem.vue"

export const requests = createResource({
	url: "hrms.api.admin_desk.get_admin_review_requests",
	params: { limit: 200 },
	auto: true,
	transform(rows) {
		return rows.map((row) => ({
			...row,
			component:
				row.doctype === "Leave Application"
					? markRaw(LeaveRequestItem)
					: markRaw(ExpenseClaimItem),
		}))
	},
})
