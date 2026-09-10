<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/holidays/approvals" />
				</ion-buttons>
				<ion-title>{{ __("Review Holidays") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Loading -->
			<div v-if="detailResource.loading" class="flex items-center justify-center h-48">
				<ion-spinner name="crescent" />
			</div>

			<div v-else-if="doc" class="p-4 pb-10">
				<!-- Employee card -->
				<div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
					<div class="flex items-center gap-4">
						<div
							class="w-14 h-14 rounded-full bg-blue-100 text-blue-700 font-bold text-lg flex items-center justify-center flex-shrink-0"
						>
							{{ initials(doc.employee_name) }}
						</div>
						<div>
							<p class="font-bold text-gray-900 text-base">{{ doc.employee_name }}</p>
							<p class="text-sm text-gray-500">{{ doc.employee }}</p>
							<p class="text-sm text-gray-500 mt-0.5">{{ __("Year:") }} {{ doc.year }}</p>
						</div>
					</div>

					<!-- Current status -->
					<div class="mt-3 pt-3 border-t border-gray-100">
						<span
							:class="[
								'inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full',
								doc.status === 'Submitted'
									? 'bg-yellow-100 text-yellow-700'
									: doc.status === 'Approved'
									? 'bg-green-100 text-green-700'
									: 'bg-red-100 text-red-700',
							]"
						>
							<FeatherIcon
								:name="doc.status === 'Submitted' ? 'clock' : doc.status === 'Approved' ? 'check-circle' : 'x-circle'"
								class="w-3.5 h-3.5"
							/>
							{{ __(doc.status) }}
						</span>
					</div>
				</div>

				<!-- Holiday dates list -->
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 px-1">
					{{ __("Holiday Dates") }} ({{ doc.holidays?.length || 0 }})
				</h3>
				<div class="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y divide-gray-50">
					<div
						v-for="(h, idx) in sortedHolidays"
						:key="h.date"
						class="flex items-center gap-3 px-4 py-3"
					>
						<span
							class="w-6 h-6 rounded-full bg-blue-50 text-blue-600 text-xs font-bold flex items-center justify-center flex-shrink-0"
						>
							{{ idx + 1 }}
						</span>
						<div>
							<p class="text-sm font-medium text-gray-800">
								{{ formatDate(h.date) }}
							</p>
							<p v-if="h.description" class="text-xs text-gray-400">
								{{ h.description }}
							</p>
						</div>
					</div>
				</div>

				<!-- Action buttons (only for Submitted status) -->
				<div v-if="doc.status === 'Submitted'" class="mt-6 flex flex-col gap-3">
					<button
						:disabled="approveResource.loading || rejectResource.loading"
						class="w-full py-3.5 rounded-xl bg-green-500 text-white font-semibold text-sm hover:bg-green-600 transition-colors disabled:opacity-50"
						@click="approve"
					>
						<span v-if="approveResource.loading">{{ __("Approving…") }}</span>
						<span v-else class="flex items-center justify-center gap-2">
							<FeatherIcon name="check-circle" class="w-4 h-4" />
							{{ __("Approve Holidays") }}
						</span>
					</button>

					<button
						:disabled="approveResource.loading || rejectResource.loading"
						class="w-full py-3.5 rounded-xl bg-red-50 text-red-600 font-semibold text-sm hover:bg-red-100 transition-colors border border-red-200 disabled:opacity-50"
						@click="confirmReject"
					>
						<span v-if="rejectResource.loading">{{ __("Rejecting…") }}</span>
						<span v-else class="flex items-center justify-center gap-2">
							<FeatherIcon name="x-circle" class="w-4 h-4" />
							{{ __("Reject") }}
						</span>
					</button>
				</div>

				<!-- Post-approval info -->
				<div
					v-if="doc.status === 'Approved' && doc.holiday_list"
					class="mt-4 bg-green-50 rounded-xl px-4 py-3"
				>
					<p class="text-sm text-green-700 font-medium">
						{{ __("Holiday List created:") }}
					</p>
					<p class="text-sm text-green-600 mt-0.5">{{ doc.holiday_list }}</p>
				</div>
			</div>

			<!-- Reject confirmation alert -->
			<ion-alert
				:is-open="showRejectAlert"
				:header="__('Reject Holidays')"
				:message="__('Are you sure you want to reject this request?')"
				:buttons="rejectAlertButtons"
				@didDismiss="showRejectAlert = false"
			/>
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
	IonAlert,
	toastController,
} from "@ionic/vue"
import { ref, computed, inject, onMounted } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { useRouter } from "vue-router"

const props = defineProps({
	id: { type: String, required: true },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()

const doc = ref(null)
const showRejectAlert = ref(false)

// ── Resources ─────────────────────────────────────────────────────────────────

const detailResource = createResource({
	url: "hrms.api.get_holiday_approval_detail",
	params: { name: props.id },
	onSuccess(data) {
		doc.value = data
	},
})

const approveResource = createResource({
	url: "hrms.api.approve_employee_holiday",
	onSuccess(data) {
		doc.value = { ...doc.value, status: "Approved", holiday_list: data.holiday_list }
		showToast(__("Holidays approved!"), "success")
	},
	onError(err) {
		showToast(err.message || __("Failed to approve"), "danger")
	},
})

const rejectResource = createResource({
	url: "hrms.api.reject_employee_holiday",
	onSuccess() {
		doc.value = { ...doc.value, status: "Rejected" }
		showToast(__("Request rejected"), "warning")
		setTimeout(() => router.back(), 1500)
	},
	onError(err) {
		showToast(err.message || __("Failed to reject"), "danger")
	},
})

// ── Computed ──────────────────────────────────────────────────────────────────

const sortedHolidays = computed(() =>
	doc.value?.holidays ? [...doc.value.holidays].sort((a, b) => (a.date > b.date ? 1 : -1)) : []
)

const rejectAlertButtons = [
	{ text: __("Cancel"), role: "cancel" },
	{
		text: __("Reject"),
		role: "destructive",
		handler: () => {
			rejectResource.submit({ name: props.id })
		},
	},
]

// ── Actions ───────────────────────────────────────────────────────────────────

function approve() {
	approveResource.submit({ name: props.id })
}

function confirmReject() {
	showRejectAlert.value = true
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(dateStr) {
	return dayjs(dateStr).format("ddd, MMM D, YYYY")
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

async function showToast(message, color = "primary") {
	const toast = await toastController.create({
		message,
		duration: 2500,
		color,
		position: "top",
	})
	await toast.present()
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
	detailResource.reload()
})
</script>
