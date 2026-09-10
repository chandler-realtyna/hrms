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
	},
	{
		name: "ScheduleApprovalDetail",
		path: "/schedule/approvals/:id",
		props: true,
		component: () => import("@/views/schedule/ScheduleApprovalDetail.vue"),
	},
]

export default routes
