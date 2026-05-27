<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/schedule/approvals" />
				</ion-buttons>
				<ion-title>{{ __("Review Schedule") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div v-if="detailResource.loading" class="flex items-center justify-center h-48">
				<ion-spinner name="crescent" />
			</div>

			<div v-else-if="doc" class="p-4 pb-10">
				<!-- Employee card -->
				<div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
					<div class="flex items-center gap-4">
						<div class="w-14 h-14 rounded-full bg-blue-100 text-blue-700 font-bold text-lg flex items-center justify-center flex-shrink-0">
							{{ initials(doc.employee_name) }}
						</div>
						<div>
							<p class="font-bold text-gray-900 text-base">{{ doc.employee_name }}</p>
							<p class="text-sm text-gray-500">{{ doc.employee }}</p>
							<p class="text-sm text-gray-500 mt-0.5">{{ __("Year:") }} {{ doc.year }} · {{ doc.timezone }}</p>
						</div>
					</div>
					<div class="mt-3 pt-3 border-t border-gray-100">
						<span :class="[
							'inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full',
							doc.status === 'Submitted' ? 'bg-yellow-100 text-yellow-700' :
							doc.status === 'Approved'  ? 'bg-green-100 text-green-700' :
							'bg-red-100 text-red-700',
						]">
							<FeatherIcon
							:name="doc.status === 'Submitted' ? 'clock' : doc.status === 'Approved' ? 'check-circle' : 'x-circle'"
							class="w-3.5 h-3.5"
						/>
							{{ __(doc.status) }}
						</span>
					</div>
				</div>

				<!-- Schedule: grouped by day -->
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 px-1">
					{{ __("Weekly Schedule") }}
				</h3>

				<div class="space-y-2">
					<div
						v-for="day in groupedDays"
						:key="day.day_of_week"
						class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
					>
						<!-- Day header -->
						<div :class="['flex items-center justify-between px-4 py-2.5 border-b border-gray-100',
							day.day_of_week >= 5 ? 'bg-gray-50' : 'bg-white']">
							<span :class="['text-sm font-semibold',
								day.day_of_week >= 5 ? 'text-gray-400' : 'text-gray-800']">
								{{ day.day_name }}
							</span>
							<span v-if="day.slots.length === 0" class="text-xs text-gray-300">{{ __("Off") }}</span>
						</div>

						<!-- Slots -->
						<div v-if="day.slots.length > 0">
							<div
								v-for="(slot, idx) in day.slots"
								:key="idx"
								:class="['flex items-center gap-3 px-4 py-2.5',
									idx < day.slots.length - 1 ? 'border-b border-gray-50' : '']"
							>
								<span :class="['text-xs font-semibold px-2 py-0.5 rounded-md',
									slot.day_type === 'Working' ? 'bg-blue-100 text-blue-700' :
									slot.day_type === 'On-Call' ? 'bg-orange-100 text-orange-700' :
									'bg-gray-100 text-gray-500']">
									{{ __(slot.day_type) }}
								</span>
								<span v-if="slot.day_type !== 'Off'" class="text-xs text-gray-600">
									{{ slot.start_time ? slot.start_time.substring(0, 5) : '—' }}
									→
									{{ slot.end_time ? slot.end_time.substring(0, 5) : '—' }}
								</span>
							</div>
						</div>
						<div v-else class="px-4 py-2.5 text-xs text-gray-300 italic">
							{{ __("No slots — off all day") }}
						</div>
					</div>
				</div>

				<!-- Action buttons -->
				<div v-if="doc.status === 'Submitted'" class="mt-6 flex flex-col gap-3">
					<button
						:disabled="approveResource.loading || rejectResource.loading"
						class="w-full py-3.5 rounded-xl bg-green-500 text-white font-semibold text-sm hover:bg-green-600 transition-colors disabled:opacity-50"
						@click="approve"
					>
						<span v-if="approveResource.loading">{{ __("Approving…") }}</span>
						<span v-else class="flex items-center justify-center gap-2">
							<FeatherIcon name="check-circle" class="w-4 h-4" />
							{{ __("Approve Schedule") }}
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
			</div>

			<ion-alert
				:is-open="showRejectAlert"
				:header="__('Reject Schedule')"
				:message="__('Are you sure you want to reject this schedule?')"
				:buttons="rejectAlertButtons"
				@didDismiss="showRejectAlert = false"
			/>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton,
	IonContent, IonSpinner, IonAlert, toastController,
} from "@ionic/vue"
import { ref, computed, inject, onMounted } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { useRouter } from "vue-router"

const props = defineProps({ id: { type: String, required: true } })
const __ = inject("$translate")
const router = useRouter()

const doc = ref(null)
const showRejectAlert = ref(false)

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

const detailResource = createResource({
	url: "hrms.api.get_schedule_approval_detail",
	params: { name: props.id },
	onSuccess(data) { doc.value = data },
})

const approveResource = createResource({
	url: "hrms.api.approve_employee_schedule",
	onSuccess() {
		doc.value = { ...doc.value, status: "Approved" }
		showToast(__("Schedule approved!"), "success")
	},
	onError(err) { showToast(err.message || __("Failed to approve"), "danger") },
})

const rejectResource = createResource({
	url: "hrms.api.reject_employee_schedule",
	onSuccess() {
		doc.value = { ...doc.value, status: "Rejected" }
		showToast(__("Schedule rejected"), "warning")
		setTimeout(() => router.back(), 1500)
	},
	onError(err) { showToast(err.message || __("Failed to reject"), "danger") },
})

// Group schedule_days rows by day_of_week
const groupedDays = computed(() => {
	const groups = {}
	for (const row of (doc.value?.schedule_days || [])) {
		const dow = Number(row.day_of_week)
		if (!groups[dow]) groups[dow] = []
		groups[dow].push(row)
	}
	return DAY_NAMES.map((name, i) => ({
		day_of_week: i,
		day_name: name,
		slots: groups[i] || [],
	}))
})

const rejectAlertButtons = [
	{ text: __("Cancel"), role: "cancel" },
	{
		text: __("Reject"),
		role: "destructive",
		handler: () => { rejectResource.submit({ name: props.id }) },
	},
]

function approve() { approveResource.submit({ name: props.id }) }
function confirmReject() { showRejectAlert.value = true }

function initials(name) {
	if (!name) return "?"
	return name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase()
}

async function showToast(message, color = "primary") {
	const toast = await toastController.create({ message, duration: 2500, color, position: "top" })
	await toast.present()
}

onMounted(() => { detailResource.reload() })
</script>
