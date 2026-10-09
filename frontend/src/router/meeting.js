export default [
	{
		path: "/meeting",
		name: "MeetingFinder",
		component: () => import("@/views/meeting/MeetingFinder.vue"),
	},
	{
		path: "/book/:slug",
		name: "BookingPage",
		component: () => import("@/views/booking/BookingPage.vue"),
		meta: { isPublic: true },
	},
	{
		path: "/calendar/connect",
		name: "CalendarConnect",
		component: () => import("@/views/calendar/CalendarConnect.vue"),
	},
]
