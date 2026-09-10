import { createResource, createListResource } from "frappe-ui"

export const unreadNotificationsCount = createResource({
	url: "/api/method/hrms.api.get_unread_notifications_count",
	initialData: 0,
	auto: false,
})

export const notifications = createListResource({
	doctype: "PWA Notification",
	fields: [
		"name",
		"from_user",
		"message",
		"read",
		"creation",
		"reference_document_type",
		"reference_document_name",
	],
	auto: false,
	orderBy: "creation desc",
	onSuccess() {
		unreadNotificationsCount.reload()
	},
})

export const arePushNotificationsEnabled = createResource({
	url: "/api/method/hrms.api.are_push_notifications_enabled",
	auto: false,
})
