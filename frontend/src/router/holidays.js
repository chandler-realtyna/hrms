const routes = [
	{
		name: "MyHolidays",
		path: "/holidays",
		component: () => import("@/views/holidays/MyHolidays.vue"),
	},
	{
		name: "HolidayApprovals",
		path: "/holidays/approvals",
		component: () => import("@/views/holidays/HolidayApprovals.vue"),
		meta: { requiresEmployee: false },
	},
	{
		name: "HolidayApprovalDetail",
		path: "/holidays/approvals/:id",
		props: true,
		component: () => import("@/views/holidays/HolidayApprovalDetail.vue"),
		meta: { requiresEmployee: false },
	},
]

export default routes
