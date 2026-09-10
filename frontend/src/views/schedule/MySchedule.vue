<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/home" /></ion-buttons>
				<ion-title>{{ __("My Schedule") }} {{ currentYear }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div v-if="!initialized" class="flex items-center justify-center h-48">
				<ion-spinner name="crescent" />
			</div>

			<div v-else class="pb-10">
				<!-- Status banner -->
				<div v-if="submission && submission.status !== 'Draft'"
					:class="['mx-4 mt-4 rounded-xl p-4 flex items-start gap-3', statusStyle.bg]">
					<FeatherIcon :name="statusStyle.icon" :class="['w-5 h-5 mt-0.5 flex-shrink-0', statusStyle.text]" />
					<div>
						<p :class="['font-semibold text-base', statusStyle.text]">{{ statusStyle.label }}</p>
						<p class="text-sm text-gray-500 mt-0.5">{{ statusStyle.sub }}</p>
					</div>
				</div>

				<!-- Timezone picker -->
				<div class="mx-4 mt-4">
					<label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
						{{ __("Your Timezone") }}
					</label>
					<select
						v-model="selectedTimezone"
						:disabled="!isEditable"
						class="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm bg-white text-gray-800 disabled:bg-gray-50 disabled:text-gray-500"
					>
						<option v-for="tz in TIMEZONES" :key="tz.value" :value="tz.value">
							{{ tz.label }}
						</option>
					</select>
					<p class="text-xs text-gray-400 mt-1">
						{{ __("Select the timezone your working hours are in.") }}
					</p>
				</div>

				<!-- Per-day slot editor -->
				<div class="mx-4 mt-5">
					<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
						{{ __("Weekly Schedule") }}
					</h3>

					<div class="space-y-3">
						<div
							v-for="day in scheduleDays"
							:key="day.day_of_week"
							class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
						>
							<!-- Day header -->
							<div :class="[
								'flex items-center justify-between px-4 py-2.5 border-b',
								day.day_of_week >= 5 ? 'bg-gray-50 border-gray-100' : 'bg-white border-gray-100',
							]">
								<div class="flex items-center gap-2">
									<span :class="[
										'text-sm font-semibold',
										day.day_of_week >= 5 ? 'text-gray-400' : 'text-gray-800',
									]">
										{{ day.day_name }}
									</span>
									<span v-if="day.slots.length === 0"
										class="text-xs text-gray-300 font-medium">
										{{ __("Off") }}
									</span>
								</div>
								<button
									v-if="isEditable"
									class="flex items-center gap-1 text-xs font-semibold text-blue-500 hover:text-blue-700 active:text-blue-800 py-1 px-2 rounded-lg hover:bg-blue-50 transition-colors"
									@click="addSlot(day)"
								>
									<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none"
										viewBox="0 0 24 24" stroke="currentColor">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
									</svg>
									{{ __("Add") }}
								</button>
							</div>

							<!-- Slots list -->
							<div v-if="day.slots.length > 0">
								<div
									v-for="(slot, slotIdx) in day.slots"
									:key="slot._id"
									:class="['flex items-center gap-2 px-3 py-2.5', slotIdx < day.slots.length - 1 ? 'border-b border-gray-50' : '']"
								>
									<!-- Type selector -->
									<select
										v-model="slot.day_type"
										:disabled="!isEditable"
										:class="['text-xs rounded-lg px-2 py-1.5 border font-semibold w-24 shrink-0',
											slot.day_type === 'Working' ? 'bg-blue-50 border-blue-200 text-blue-700' :
											slot.day_type === 'On-Call' ? 'bg-orange-50 border-orange-200 text-orange-700' :
											'bg-gray-50 border-gray-200 text-gray-500',
											!isEditable ? 'opacity-60' : '']"
									>
										<option value="Working">{{ __("Work") }}</option>
										<option value="On-Call">{{ __("On-Call") }}</option>
										<option value="Off">{{ __("Off") }}</option>
									</select>

									<!-- Start time -->
									<input
										type="time"
										v-model="slot.start_time"
										:disabled="!isEditable || slot.day_type === 'Off'"
										class="flex-1 min-w-0 text-xs rounded-lg px-2 py-1.5 border border-gray-200 disabled:bg-gray-50 disabled:text-gray-400"
									/>

									<span class="text-xs text-gray-300 shrink-0">→</span>

									<!-- End time -->
									<input
										type="time"
										v-model="slot.end_time"
										:disabled="!isEditable || slot.day_type === 'Off'"
										class="flex-1 min-w-0 text-xs rounded-lg px-2 py-1.5 border border-gray-200 disabled:bg-gray-50 disabled:text-gray-400"
									/>

									<!-- Remove button -->
									<button
										v-if="isEditable"
										class="shrink-0 p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors"
										@click="removeSlot(day, slotIdx)"
									>
										<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none"
											viewBox="0 0 24 24" stroke="currentColor">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
												d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
										</svg>
									</button>
								</div>
							</div>

							<!-- Empty day: no slots placeholder -->
							<div v-else-if="!isEditable" class="px-4 py-3 text-xs text-gray-300 italic">
								{{ __("No slots — off all day") }}
							</div>
						</div>
					</div>
				</div>

				<!-- Action buttons -->
				<div v-if="isEditable" class="mx-4 mt-6 flex flex-col gap-3">
					<button
						:disabled="saveDraftResource.loading"
						class="w-full py-3 rounded-xl border border-gray-300 text-gray-700 font-medium text-sm hover:bg-gray-50 disabled:opacity-50"
						@click="saveDraft"
					>
						{{ saveDraftResource.loading ? __("Saving…") : __("Save Draft") }}
					</button>
					<button
						:disabled="submitResource.loading"
						class="w-full py-3 rounded-xl bg-blue-500 text-white font-medium text-sm hover:bg-blue-600 disabled:opacity-50"
						@click="submitSchedule"
					>
						{{ submitResource.loading ? __("Submitting…") : __("Submit for Approval") }}
					</button>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton,
	IonContent, IonSpinner, toastController } from "@ionic/vue"
import { ref, computed, inject, onMounted } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"
import { getViewerTimezone, getUtcOffsetMinutes } from "../../utils/timezone"

const __ = inject("$translate")

const currentYear = new Date().getFullYear()
const initialized = ref(false)
const submission = ref(null)
const selectedTimezone = ref(getViewerTimezone())

// ── Timezones (fetched from Frappe) ────────────────────────────────────────────

const _rawTimezones = ref([])

const TIMEZONES = computed(() => {
	const now = new Date()
	return [..._rawTimezones.value]
		.sort((a, b) => {
			const diff = getUtcOffsetMinutes(a, now) - getUtcOffsetMinutes(b, now)
			return diff !== 0 ? diff : a.localeCompare(b)
		})
		.map(tz => {
			const mins = getUtcOffsetMinutes(tz, now)
			const sign = mins >= 0 ? "+" : "-"
			const abs = Math.abs(mins)
			const hh = String(Math.floor(abs / 60)).padStart(2, "0")
			const mm = String(abs % 60).padStart(2, "0")
			return { value: tz, label: `(UTC${sign}${hh}:${mm}) ${tz.replace(/_/g, " ")}` }
		})
})

const timezonesResource = createResource({
	url: "frappe.core.doctype.user.user.get_timezones",
	onSuccess(data) {
		_rawTimezones.value = data.timezones || []
	},
})

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

// ── State ──────────────────────────────────────────────────────────────────────

let _slotSeq = 0
function makeSlot(day_type = "Working", start_time = "09:00", end_time = "17:00") {
	return { _id: ++_slotSeq, day_type, start_time, end_time }
}

function defaultScheduleDays() {
	return DAY_NAMES.map((name, i) => ({
		day_of_week: i,
		day_name: name,
		// Mon–Fri: one Working slot; Sat–Sun: no slots
		slots: i < 5 ? [makeSlot("Working", "09:00", "17:00")] : [],
	}))
}

const scheduleDays = ref(defaultScheduleDays())

const isEditable = computed(() =>
	initialized.value && (!submission.value || submission.value.status === "Draft")
)

const statusStyle = computed(() => {
	const s = submission.value?.status
	if (s === "Submitted") return { bg: "bg-yellow-50", text: "text-yellow-700", icon: "clock",        label: __("Pending Approval"), sub: __("HR will review your schedule shortly.") }
	if (s === "Approved")  return { bg: "bg-green-50",  text: "text-green-700",  icon: "check-circle", label: __("Approved"),          sub: __("Your schedule has been approved.") }
	if (s === "Rejected")  return { bg: "bg-red-50",    text: "text-red-700",    icon: "x-circle",     label: __("Rejected"),          sub: __("Your schedule was rejected. Please contact HR.") }
	return {}
})

// ── Slot helpers ───────────────────────────────────────────────────────────────

function addSlot(day) {
	// Default start = end of last slot, or 09:00 if none
	const last = day.slots[day.slots.length - 1]
	const startTime = last?.end_time || "09:00"
	// Compute 1h later as default end
	const [h, m] = startTime.split(":").map(Number)
	const endH = Math.min(h + 1, 23)
	const endTime = `${String(endH).padStart(2, "0")}:${String(m).padStart(2, "0")}`
	day.slots.push(makeSlot("Working", startTime, endTime))
}

function removeSlot(day, slotIdx) {
	day.slots.splice(slotIdx, 1)
}

// ── Payload helpers ────────────────────────────────────────────────────────────

function buildDaysPayload() {
	const rows = []
	for (const day of scheduleDays.value) {
		for (const slot of day.slots) {
			rows.push({
				day_of_week: day.day_of_week,
				day_name: day.day_name,
				day_type: slot.day_type,
				start_time: slot.day_type !== "Off" ? (slot.start_time + ":00").substring(0, 8) : null,
				end_time:   slot.day_type !== "Off" ? (slot.end_time   + ":00").substring(0, 8) : null,
			})
		}
	}
	return rows
}

function loadFromDoc(doc) {
	submission.value = doc
	selectedTimezone.value = doc.timezone || getViewerTimezone()

	// Group rows from doc by day_of_week
	const grouped = {}
	for (const row of (doc.schedule_days || [])) {
		const dow = int(row.day_of_week)
		if (!grouped[dow]) grouped[dow] = []
		grouped[dow].push(
			makeSlot(
				row.day_type || "Working",
				row.start_time ? String(row.start_time).substring(0, 5) : "09:00",
				row.end_time   ? String(row.end_time).substring(0, 5)   : "17:00",
			)
		)
	}

	scheduleDays.value = DAY_NAMES.map((name, i) => ({
		day_of_week: i,
		day_name: name,
		slots: grouped[i] || [],
	}))
}

// JS equivalent of Python int() — just Number()
function int(v) { return Number(v) }

// ── Resources ──────────────────────────────────────────────────────────────────

const scheduleRecord = createResource({
	url: "hrms.api.get_my_schedule",
	params: { year: String(currentYear) },
	onSuccess(data) {
		if (data) loadFromDoc(data)
		initialized.value = true
	},
	onError() { initialized.value = true },
})

const saveDraftResource = createResource({
	url: "hrms.api.save_schedule_draft",
	onSuccess(data) {
		loadFromDoc(data)
		showToast(__("Draft saved"), "success")
	},
	onError(err) { showToast(err.message || __("Failed to save"), "danger") },
})

const submitResource = createResource({
	url: "hrms.api.submit_employee_schedule",
	onSuccess(data) {
		loadFromDoc(data)
		showToast(__("Schedule submitted for approval!"), "success")
	},
	onError(err) { showToast(err.message || __("Failed to submit"), "danger") },
})

// ── Actions ────────────────────────────────────────────────────────────────────

function saveDraft() {
	saveDraftResource.submit({
		year: String(currentYear),
		timezone: selectedTimezone.value,
		days: JSON.stringify(buildDaysPayload()),
	})
}

function submitSchedule() {
	if (!submission.value?.name) {
		createResource({
			url: "hrms.api.save_schedule_draft",
			onSuccess(data) {
				loadFromDoc(data)
				submitResource.submit({ name: data.name })
			},
			onError(err) { showToast(err.message || __("Failed to save"), "danger") },
		}).submit({
			year: String(currentYear),
			timezone: selectedTimezone.value,
			days: JSON.stringify(buildDaysPayload()),
		})
	} else {
		submitResource.submit({ name: submission.value.name })
	}
}

async function showToast(message, color = "primary") {
	const toast = await toastController.create({ message, duration: 2500, color, position: "top" })
	await toast.present()
}

onMounted(() => {
	timezonesResource.reload()
	scheduleRecord.reload()
})
</script>
