import { createRouter, createWebHistory } from "@ionic/vue-router"

import TabbedView from "@/views/TabbedView.vue"
import leaveRoutes from "./leaves"
import claimRoutes from "./claims"
import employeeAdvanceRoutes from "./advances"
import invoiceRoutes from "./invoices"
import timesheetRoutes from "./timesheets"
import holidayRoutes from "./holidays"
import scheduleRoutes from "./schedule"
import availabilityRoutes from "./availability"
import docsRoutes from "./docs"
import meetingRoutes from "./meeting"

const routes = [
	{
		path: "/",
		redirect: "/timesheets/timer",
	},
	{
		path: "/",
		component: TabbedView,
		children: [
			{
				path: "",
				redirect: "/timesheets/timer",
			},
			{
				path: "/home",
				name: "Home",
				component: () => import("@/views/Home.vue"),
			},
			{
				path: "/timesheets/timer",
				name: "TimesheetTimer",
				component: () => import("@/views/timesheet/Timer.vue"),
			},
			// NOTE: every child of TabbedView must own a bottom tab, or the
			// tab outlet can keep showing a stale view while the URL changes.
			// Dashboards without tabs live as top-level routes below.
			// Tab pages: nested under TabbedView so the bottom tabs stay
			// mounted and working on mobile.
			...timesheetRoutes,
			...availabilityRoutes,
		],
	},
	{
		path: "/dashboard/leaves",
		name: "LeavesDashboard",
		component: () => import("@/views/leave/Dashboard.vue"),
	},
	{
		path: "/dashboard/expense-claims",
		name: "ExpenseClaimsDashboard",
		component: () => import("@/views/expense_claim/Dashboard.vue"),
	},
	{
		path: "/dashboard/salary-slips",
		redirect: "/dashboard/invoices",
	},
	{
		path: "/dashboard/invoices",
		name: "InvoicesDashboard",
		component: () => import("@/views/invoice/List.vue"),
	},
	{
		path: "/login",
		name: "Login",
		component: () => import("@/views/Login.vue"),
	},
	{
		path: "/forgot-password",
		name: "ForgotPassword",
		component: () => import("@/views/ForgotPassword.vue"),
	},
	{
		path: "/profile",
		name: "Profile",
		component: () => import("@/views/Profile.vue"),
	},
	{
		path: "/notifications",
		name: "Notifications",
		component: () => import("@/views/Notifications.vue"),
	},
	{
		path: "/settings",
		name: "Settings",
		component: () => import("@/views/AppSettings.vue"),
	},
	{
		path: "/change-password",
		name: "ChangePassword",
		component: () => import("@/views/ChangePassword.vue"),
	},
	{
		path: "/invalid-employee",
		name: "InvalidEmployee",
		component: () => import("@/views/InvalidEmployee.vue"),
	},
	...leaveRoutes,
	...claimRoutes,
	...employeeAdvanceRoutes,
	...invoiceRoutes,
	...holidayRoutes,
	...scheduleRoutes,
	...docsRoutes,
	...meetingRoutes,
]

const router = createRouter({
	history: createWebHistory("/hrms"),
	routes,
})

// If a lazily-loaded view chunk fails to load (e.g. a deploy replaced the
// hashed bundle files while the app was open), the router outlet would
// otherwise keep showing the previous page forever — same URL, wrong content,
// and tapping the tab again is a no-op. Reload once to fetch the fresh bundle.
const CHUNK_LOAD_FAILURE =
	/Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk .* failed|Loading CSS chunk/i

router.onError((err) => {
	try {
		if (!CHUNK_LOAD_FAILURE.test(err?.message || "")) return
		const last = Number(sessionStorage.getItem("hrms_chunk_reload_at") || 0)
		if (Date.now() - last < 30000) return
		sessionStorage.setItem("hrms_chunk_reload_at", String(Date.now()))
		window.location.reload()
	} catch {
		// never break routing because of the recovery itself
	}
})

export default router
