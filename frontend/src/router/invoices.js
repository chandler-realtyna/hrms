const routes = [
	{
		name: "EmployeeInvoiceListView",
		path: "/invoices",
		component: () => import("@/views/invoice/List.vue"),
	},
	{
		name: "EmployeeInvoiceNewView",
		path: "/invoices/new",
		component: () => import("@/views/invoice/Form.vue"),
	},
	{
		name: "EmployeeInvoiceDetailView",
		path: "/invoices/:id",
		props: true,
		component: () => import("@/views/invoice/Form.vue"),
	},
	{
		path: "/salary-slips/:id",
		redirect: "/invoices",
	},
]

export default routes
