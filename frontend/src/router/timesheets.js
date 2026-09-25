const routes = [
	{
		name: "TimesheetListView",
		path: "/timesheets",
		component: () => import("@/views/timesheet/List.vue"),
	},
	// NOTE: TimesheetTimer lives under TabbedView in router/index.js so it
	// renders inside the bottom-tab outlet (it's the default tab).
	{
		name: "TimesheetProjectApprovals",
		path: "/timesheets/approvals",
		component: () => import("@/views/timesheet/Approvals.vue"),
	},
	{
		name: "TimesheetFormView",
		path: "/timesheets/new",
		component: () => import("@/views/timesheet/Form.vue"),
	},
	{
		name: "TimesheetDetailView",
		path: "/timesheets/:id",
		props: true,
		component: () => import("@/views/timesheet/Form.vue"),
	},
]
export default routes
