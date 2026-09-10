<template>
	<ion-page>
		<ion-content class="ion-padding">
			<div class="flex flex-col h-screen w-screen">
				<div class="w-full sm:w-96">
					<header
						class="flex flex-row bg-white shadow-sm py-4 px-3 items-center justify-between border-b sticky top-0 z-10"
					>
						<div class="flex flex-row items-center">
							<Button variant="ghost" class="!pl-0 hover:bg-white" @click="router.back()">
								<FeatherIcon name="chevron-left" class="h-5 w-5" />
							</Button>
							<h2 class="text-xl font-semibold text-gray-900">{{ __("Settings") }}</h2>
						</div>
					</header>

					<div class="flex flex-col gap-5 my-4 w-full p-4">
						<div class="flex flex-col gap-4 rounded-xl bg-white p-4">
							<ProfileImageEditor />
							<router-link
								:to="{ name: 'Profile' }"
								class="flex items-center justify-between border-t pt-4 text-gray-800"
							>
								<span class="flex items-center gap-3">
									<FeatherIcon name="user" class="h-5 w-5 text-gray-500" />
									<span>{{ __("Open profile") }}</span>
								</span>
								<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
							</router-link>
						</div>

						<!-- Push Notifications -->
						<div class="flex flex-col bg-white rounded">
							<div
								class="flex flex-row cursor-pointer flex-start p-4 items-center justify-between border-b"
							>
								<router-link
									:to="{ name: 'ChangePassword' }"
									class="flex flex-row items-center justify-between w-full"
								>
									<div class="flex flex-row items-center gap-3 grow">
										<FeatherIcon name="lock" class="h-5 w-5 text-gray-500" />
										<div class="text-base font-normal text-gray-800">
											{{ __("Change Password") }}
										</div>
									</div>
									<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
								</router-link>
							</div>
						</div>

						<div v-if="pushFeatureAvailable" class="flex flex-col bg-white rounded">
							<Switch
								size="md"
								:label="__('Enable Push Notifications')"
								:class="description ? 'p-2' : ''"
								:model-value="pushNotificationState"
								:disabled="disablePushSetting"
								:description="description"
								@update:model-value="togglePushNotifications"
							/>
						</div>

						<div
							v-if="pushFeatureAvailable && isLoading"
							class="flex -mt-2 items-center justify-center gap-2"
						>
							<LoadingIndicator class="w-3 h-3 text-gray-800" />
							<span class="text-gray-900 text-sm">
								{{
									pushNotificationState
										? __("Disabling Push Notifications...")
										: __("Enabling Push Notifications...")
								}}
							</span>
						</div>

						<!-- Dark Mode -->
						<div class="flex flex-col bg-white rounded">
							<Switch
								size="md"
								:label="__('Dark Mode')"
								:model-value="isDark"
								@update:model-value="toggleDarkMode"
							/>
						</div>

						<!-- Google Calendar -->
						<div class="bg-white rounded-xl border border-gray-100 p-4 space-y-4">
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-2">
									<FeatherIcon name="calendar" class="w-4 h-4 text-gray-500" />
									<h3 class="font-semibold text-gray-900 text-sm">{{ __("Google Calendar") }}</h3>
								</div>
								<span
									:class="[
										'text-xs font-semibold px-2.5 py-1 rounded-full',
										calendarStatus.data?.is_connected
											? 'bg-green-100 text-green-700'
											: 'bg-gray-100 text-gray-500',
									]"
								>
									{{ calendarStatus.data?.is_connected ? __("Connected") : __("Not Connected") }}
								</span>
							</div>

							<Button
								v-if="!calendarStatus.data?.is_connected"
								variant="subtle"
								class="w-full"
								@click="goToCalendarConnect"
							>
								<template #prefix><FeatherIcon name="external-link" class="w-4 h-4" /></template>
								{{ __("Connect Google Calendar") }}
							</Button>

							<!-- Booking settings (only when connected) -->
							<template v-if="calendarStatus.data?.is_connected">
								<div class="border-t border-gray-100 pt-4 space-y-3">
									<div class="flex items-center justify-between">
										<div>
											<p class="text-sm font-medium text-gray-800">
												{{ __("Public Booking Page") }}
											</p>
											<p class="text-xs text-gray-400">
												{{ __("Let anyone book time with you") }}
											</p>
										</div>
										<Switch
											size="sm"
											:model-value="bookingEnabled"
											@update:model-value="bookingEnabled = $event"
										/>
									</div>

									<div v-if="bookingEnabled">
										<label class="block text-xs font-medium text-gray-600 mb-1">{{
											__("Booking URL Slug")
										}}</label>
										<div class="flex items-center gap-2">
											<span class="text-xs text-gray-400 shrink-0">/book/</span>
											<input
												v-model="bookingSlug"
												type="text"
												class="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
												:placeholder="__('your-name')"
											/>
										</div>
										<div
											v-if="bookingSlug"
											class="flex items-center gap-2 mt-1 bg-gray-50 rounded-lg px-3 py-2"
										>
											<span class="text-xs text-gray-500 truncate flex-1"
												>/hrms/book/{{ bookingSlug }}</span
											>
											<button
												@click="copyBookingUrl"
												class="text-gray-400 hover:text-blue-600 shrink-0"
												:title="__('Copy link')"
											>
												<FeatherIcon name="copy" class="w-3.5 h-3.5" />
											</button>
											<a
												:href="`/hrms/book/${bookingSlug}`"
												target="_blank"
												class="text-gray-400 hover:text-blue-600 shrink-0"
												:title="__('Open booking page')"
											>
												<FeatherIcon name="external-link" class="w-3.5 h-3.5" />
											</a>
										</div>
									</div>

									<div class="grid grid-cols-2 gap-3">
										<div>
											<label class="block text-xs font-medium text-gray-600 mb-1">{{
												__("Min Notice (hrs)")
											}}</label>
											<input
												v-model.number="minNoticeHours"
												type="number"
												min="0"
												class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
											/>
										</div>
										<div>
											<label class="block text-xs font-medium text-gray-600 mb-1">{{
												__("Durations (min)")
											}}</label>
											<input
												v-model="slotDurationOptions"
												type="text"
												placeholder="30,60"
												class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
											/>
										</div>
									</div>

									<Button
										variant="solid"
										class="w-full"
										:loading="savingSettings"
										@click="saveSettings"
									>
										{{ __("Save Booking Settings") }}
									</Button>
								</div>
							</template>
						</div>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { useRouter } from "vue-router"
import {
	FeatherIcon,
	Switch,
	toast,
	LoadingIndicator,
	createResource,
	call,
	Button,
} from "frappe-ui"

import { computed, inject, ref, watch } from "vue"

import { arePushNotificationsEnabled } from "@/data/notifications"
import { useDarkMode } from "@/utils/darkMode"
import ProfileImageEditor from "@/components/ProfileImageEditor.vue"

const __ = inject("$translate")
const router = useRouter()
const { isDark, toggleDarkMode } = useDarkMode()

const goToCalendarConnect = () => {
	window.location.href = "/hrms/calendar/connect"
}

const copyBookingUrl = () => {
	const url = `${window.location.origin}/hrms/book/${bookingSlug.value}`
	navigator.clipboard.writeText(url).then(() => {
		toast({
			title: __("Copied!"),
			text: url,
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	})
}

// Google Calendar status
const calendarStatus = createResource({
	url: "hrms.api.calendar.get_calendar_connection_status",
	auto: true,
})

const bookingSettings = createResource({
	url: "hrms.api.calendar.get_booking_settings",
	auto: true,
	onSuccess(data) {
		bookingSlug.value = data.booking_slug || ""
		bookingEnabled.value = Boolean(data.booking_enabled)
		minNoticeHours.value = data.min_notice_hours ?? 1
		slotDurationOptions.value = data.slot_duration_options || "30,60"
	},
})

const bookingSlug = ref("")
const bookingEnabled = ref(false)
const minNoticeHours = ref(1)
const slotDurationOptions = ref("30,60")
const savingSettings = ref(false)

async function saveSettings() {
	savingSettings.value = true
	try {
		await call("hrms.api.calendar.save_booking_settings", {
			booking_slug: bookingSlug.value.trim().toLowerCase(),
			booking_enabled: bookingEnabled.value ? 1 : 0,
			min_notice_hours: minNoticeHours.value,
			slot_duration_options: slotDurationOptions.value,
		})
		toast({
			title: __("Saved"),
			text: __("Booking settings updated"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (e) {
		toast({
			title: __("Error"),
			text: e?.message || __("Failed to save settings"),
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	} finally {
		savingSettings.value = false
	}
}

const pushNotificationState = ref(window.frappePushNotification?.isNotificationEnabled())
const isLoading = ref(false)

const pushFeatureAvailable = computed(() => {
	return Boolean(window.frappe?.boot.push_relay_server_url && arePushNotificationsEnabled.data)
})

const disablePushSetting = computed(() => {
	return !pushFeatureAvailable.value || isLoading.value
})

const description = computed(() => {
	return pushFeatureAvailable.value ? "" : __("Push notifications have been disabled on your site")
})

const togglePushNotifications = (newValue) => {
	if (newValue) {
		enablePushNotifications()
	} else {
		isLoading.value = true
		window.frappePushNotification
			.disableNotification()
			.then(() => {
				pushNotificationState.value = false
				toast({
					title: __("Success"),
					text: __("Push notifications disabled"),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			})
			.catch((error) => {
				toast({
					title: __("Error"),
					text: __(error.message),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			})
			.finally(() => {
				isLoading.value = false
			})
	}
}
const enablePushNotifications = () => {
	isLoading.value = true

	window.frappePushNotification
		.enableNotification()
		.then((data) => {
			if (data.permission_granted) {
				pushNotificationState.value = true
			} else {
				toast({
					title: __("Error"),
					text: __("Push Notification permission denied"),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
				pushNotificationState.value = false
			}
		})
		.catch((error) => {
			toast({
				title: __("Error"),
				text: __(error.message),
				icon: "alert-circle",
				position: "bottom-center",
				iconClasses: "text-red-500",
			})
			pushNotificationState.value = false
		})
		.finally(() => {
			isLoading.value = false
		})
}
</script>
