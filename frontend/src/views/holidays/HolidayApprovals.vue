<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>{{ __("Holiday Approvals") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Loading -->
			<div v-if="approvalsResource.loading" class="flex items-center justify-center h-48">
				<ion-spinner name="crescent" />
			</div>

			<!-- Empty state -->
			<div
				v-else-if="!approvalsResource.data || approvalsResource.data.length === 0"
				class="flex flex-col items-center justify-center h-64 gap-3 text-gray-400"
			>
				<FeatherIcon name="umbrella" class="w-12 h-12 text-gray-300" />
				<p class="text-base font-medium">{{ __("No pending approvals") }}</p>
				<p class="text-sm">{{ __("All holiday requests have been reviewed.") }}</p>
			</div>

			<!-- List -->
			<div v-else class="p-4 space-y-3">
				<div
					v-for="item in approvalsResource.data"
					:key="item.name"
					class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
					@click="goToDetail(item.name)"
				>
					<div class="p-4 flex items-center gap-3">
						<!-- Avatar -->
						<div
							class="w-10 h-10 rounded-full bg-blue-100 text-blue-700 font-bold text-sm flex items-center justify-center flex-shrink-0"
						>
							{{ initials(item.employee_name) }}
						</div>
						<!-- Info -->
						<div class="flex-1 min-w-0">
							<p class="font-semibold text-gray-900 truncate">
								{{ item.employee_name }}
							</p>
							<p class="text-xs text-gray-500 mt-0.5">
								{{ item.employee }} · {{ item.year }}
							</p>
						</div>
						<!-- Badge -->
						<span
							class="flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full bg-yellow-100 text-yellow-700"
						>
							{{ __("Pending") }}
						</span>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-4 w-4 text-gray-400 flex-shrink-0"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9 5l7 7-7 7"
							/>
						</svg>
					</div>
				</div>
			</div>

			<!-- Pull-to-refresh hint -->
			<ion-refresher slot="fixed" @ionRefresh="refresh($event)">
				<ion-refresher-content />
			</ion-refresher>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage,
	IonHeader,
	IonToolbar,
	IonTitle,
	IonButtons,
	IonBackButton,
	IonContent,
	IonSpinner,
	IonRefresher,
	IonRefresherContent,
} from "@ionic/vue"
import { inject, onMounted } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { useRouter } from "vue-router"

const __ = inject("$translate")
const router = useRouter()

const approvalsResource = createResource({
	url: "hrms.api.get_pending_holiday_approvals",
	onError() {},
})

function goToDetail(name) {
	router.push({ name: "HolidayApprovalDetail", params: { id: name } })
}

function initials(name) {
	if (!name) return "?"
	return name
		.split(" ")
		.slice(0, 2)
		.map((n) => n[0])
		.join("")
		.toUpperCase()
}

async function refresh(event) {
	await approvalsResource.reload()
	event.target.complete()
}

onMounted(() => {
	approvalsResource.reload()
})
</script>
