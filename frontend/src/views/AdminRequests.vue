<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/desk" />
				</ion-buttons>
				<ion-title>{{ title }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<main class="mx-auto w-full max-w-4xl p-4 md:p-6">
				<div class="mb-5">
					<h1 class="text-lg font-semibold text-gray-900">{{ title }}</h1>
					<p class="mt-1 text-sm text-gray-500">{{ __("Requests assigned to you for review") }}</p>
				</div>

				<div v-if="requests.loading" class="rounded border bg-white p-8 text-center text-sm text-gray-500">
					{{ __("Loading requests…") }}
				</div>
				<div v-else-if="requests.error" class="rounded border border-red-200 bg-white p-6 text-sm text-red-700">
					{{ __("You do not have permission to review these requests.") }}
				</div>
				<div v-else-if="!items.length" class="rounded border bg-white p-8 text-center text-sm text-gray-500">
					{{ __("No requests are waiting for your review.") }}
				</div>
				<div v-else class="mt-5 flex flex-col gap-3">
					<button
						v-for="request in items"
						:key="request.name"
						class="flex w-full items-center justify-between gap-4 rounded border bg-white p-4 text-left hover:bg-gray-50"
						@click="selectedRequest = request"
					>
						<span class="min-w-0">
							<span class="block truncate text-sm font-medium text-gray-900">
								{{ request.employee_name || request.employee }}
							</span>
							<span class="mt-1 block truncate text-sm text-gray-600">
								{{ requestSummary(request) }}
							</span>
							<span class="mt-1 block text-xs text-gray-500">
								{{ requestDate(request) }} · {{ request.name }}
							</span>
						</span>
						<Badge variant="outline" :label="requestStatus(request)" size="md" />
					</button>
				</div>
			</main>
		</ion-content>

		<ion-modal :is-open="Boolean(selectedRequest)" @didDismiss="selectedRequest = null">
			<RequestActionSheet
				v-if="selectedRequest"
				:fields="fieldsByDoctype[selectedRequest.doctype]"
				v-model="selectedRequest"
			/>
		</ion-modal>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { useRoute } from "vue-router"
import { IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonModal, onIonViewWillEnter } from "@ionic/vue"
import { Badge } from "frappe-ui"

import RequestActionSheet from "@/components/RequestActionSheet.vue"
import { EXPENSE_CLAIM_FIELDS, LEAVE_FIELDS } from "@/data/config/requestSummaryFields"
import { requests } from "@/data/adminRequests"

const __ = inject("$translate")
const route = useRoute()
const requestType = computed(() => route.meta.requestType)
const title = computed(() =>
	__(requestType.value === "Leave Application" ? "Leave Requests" : "Expense Requests")
)
const items = computed(() => (requests.data || []).filter((row) => row.doctype === requestType.value))
const selectedRequest = ref(null)
const fieldsByDoctype = {
	"Leave Application": LEAVE_FIELDS,
	"Expense Claim": EXPENSE_CLAIM_FIELDS,
}

const requestSummary = (request) =>
	request.doctype === "Leave Application"
		? request.leave_type
		: request.expense_type || request.company

const requestDate = (request) =>
	request.doctype === "Leave Application"
		? request.leave_dates || `${request.from_date} – ${request.to_date}`
		: request.from_date && request.to_date
			? `${request.from_date} – ${request.to_date}`
			: request.posting_date

const requestStatus = (request) =>
	request[request.workflow_state_field] || request.approval_status || request.status

onIonViewWillEnter(() => requests.reload())
</script>
