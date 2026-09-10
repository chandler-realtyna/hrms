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
	},
	{
		name: "HolidayApprovalDetail",
		path: "/holidays/approvals/:id",
		props: true,
		component: () => import("@/views/holidays/HolidayApprovalDetail.vue"),
	},
]

export default routes
