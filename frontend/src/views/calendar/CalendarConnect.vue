<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/home" /></ion-buttons>
				<ion-title>{{ __("Connect Google Calendar") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content class="ion-padding">
			<div class="flex flex-col items-center justify-center h-full gap-6 max-w-sm mx-auto text-center">

				<!-- Success state -->
				<template v-if="connected">
					<div class="w-20 h-20 rounded-2xl bg-green-50 flex items-center justify-center">
						<FeatherIcon name="check-circle" class="w-10 h-10 text-green-600" />
					</div>
					<div>
						<h2 class="text-xl font-bold text-gray-900">{{ __("Google Calendar Connected!") }}</h2>
						<p class="mt-2 text-sm text-gray-500">
							{{ __("Your calendar is now linked. You can manage settings from the Settings page.") }}
						</p>
					</div>
					<Button variant="solid" class="w-full" @click="goToSettings">
						{{ __("Go to Settings") }}
					</Button>
				</template>

				<!-- Connect state -->
				<template v-else>
					<div class="w-20 h-20 rounded-2xl bg-blue-50 flex items-center justify-center">
						<svg class="w-10 h-10 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
							<path d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 16H5V10h14v10zM5 8V6h14v2H5z"/>
						</svg>
					</div>

					<div>
						<h2 class="text-xl font-bold text-gray-900">{{ __("Connect Google Calendar") }}</h2>
						<p class="mt-2 text-sm text-gray-500">
							{{ __("Link your Google Calendar so the system can check your availability, show free time slots, and automatically add meetings to your calendar.") }}
						</p>
					</div>

					<div class="w-full space-y-3 text-left bg-gray-50 rounded-xl p-4">
						<div class="flex items-start gap-3">
							<FeatherIcon name="check-circle" class="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
							<p class="text-sm text-gray-700">{{ __("Allow others to book time with you via your public booking page") }}</p>
						</div>
						<div class="flex items-start gap-3">
							<FeatherIcon name="check-circle" class="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
							<p class="text-sm text-gray-700">{{ __("Find meeting times that work for the whole team") }}</p>
						</div>
						<div class="flex items-start gap-3">
							<FeatherIcon name="check-circle" class="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
							<p class="text-sm text-gray-700">{{ __("Meeting invitations are added directly to your Google Calendar") }}</p>
						</div>
					</div>

					<div v-if="error" class="w-full bg-red-50 border border-red-100 rounded-xl p-3 text-sm text-red-600">
						{{ error }}
					</div>

					<Button
						variant="solid"
						class="w-full"
						:loading="loading"
						@click="connectCalendar"
					>
						<template #prefix>
							<FeatherIcon name="external-link" class="w-4 h-4" />
						</template>
						{{ __("Connect Google Calendar") }}
					</Button>

					<p v-if="polling" class="text-sm text-gray-400">
						{{ __("Waiting for Google authorization…") }}
					</p>
				</template>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons, IonBackButton } from "@ionic/vue"
import { FeatherIcon, call } from "frappe-ui"
import { inject, ref, onUnmounted } from "vue"

const __ = inject("$translate")
const loading = ref(false)
const error = ref("")
const connected = ref(false)
const polling = ref(false)

let pollInterval = null
let popupMonitorInterval = null
let popup = null

const stopPolling = () => {
	if (pollInterval) {
		clearInterval(pollInterval)
		pollInterval = null
	}
	if (popupMonitorInterval) {
		clearInterval(popupMonitorInterval)
		popupMonitorInterval = null
	}
	polling.value = false
}

const checkConnection = async () => {
	try {
		const status = await call("hrms.api.calendar.get_calendar_connection_status")
		if (status?.is_connected) {
			stopPolling()
			connected.value = true
			return true
		}
	} catch (_) {}
	return false
}

const startPolling = () => {
	polling.value = true

	// Poll every 2.5s as a background check
	pollInterval = setInterval(checkConnection, 2500)

	// Also watch for the popup closing so we can give immediate feedback
	popupMonitorInterval = setInterval(async () => {
		if (!popup || popup.closed) {
			clearInterval(popupMonitorInterval)
			popupMonitorInterval = null
			const isConnected = await checkConnection()
			if (!isConnected) {
				stopPolling()
				error.value = __("Connection was not completed. Please try again.")
			}
		}
	}, 500)
}

const onMessage = async (event) => {
	if (event.data?.type === "google_calendar_connected") {
		await checkConnection()
	}
}

const connectCalendar = async () => {
	loading.value = true
	error.value = ""
	stopPolling()

	try {
		const result = await call("hrms.api.calendar.get_google_calendar_authorize_url")
		const authUrl = result?.auth_url
		if (!authUrl) throw new Error("No authorization URL returned")

		popup = window.open(authUrl, "_blank", "width=600,height=700")
		window.addEventListener("message", onMessage)
		startPolling()
	} catch (e) {
		error.value = e?.message || __("Failed to initiate Google Calendar connection")
	} finally {
		loading.value = false
	}
}

const goToSettings = () => {
	window.location.href = "/hrms/settings"
}

onUnmounted(() => {
	stopPolling()
	window.removeEventListener("message", onMessage)
})
</script>
