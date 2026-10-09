const routes = [
	{
		name: "MySchedule",
		path: "/schedule",
		component: () => import("@/views/schedule/MySchedule.vue"),
	},
	{
		name: "ScheduleApprovals",
		path: "/schedule/approvals",
		component: () => import("@/views/schedule/ScheduleApprovals.vue"),
		meta: { requiresEmployee: false },
	},
	{
		name: "ScheduleApprovalDetail",
		path: "/schedule/approvals/:id",
		props: true,
		component: () => import("@/views/schedule/ScheduleApprovalDetail.vue"),
		meta: { requiresEmployee: false },
	},
]

export default routes
