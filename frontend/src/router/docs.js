const routes = [
	{
		path: "/docs",
		name: "Docs",
		component: () => import("@/views/docs/Docs.vue"),
	},
	{
		path: "/docs/new",
		name: "DocsForm",
		component: () => import("@/views/docs/DocForm.vue"),
	},
]

export default routes
