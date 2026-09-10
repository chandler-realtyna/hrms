<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>{{ __("My Holidays") }} {{ currentYear }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Loading / not yet initialised -->
			<div
				v-if="!initialized || holidayRecord.loading"
				class="flex items-center justify-center h-48"
			>
				<ion-spinner name="crescent" />
			</div>

			<div v-else-if="initialized" class="pb-10">
				<!-- ── Status Banner (Submitted / Approved / Rejected) ── -->
				<div
					v-if="submission && submission.status !== 'Draft'"
					:class="['mx-4 mt-4 rounded-xl p-4 flex items-start gap-3', statusStyle.bg]"
				>
					<FeatherIcon
						:name="statusStyle.icon"
						:class="['w-5 h-5 mt-0.5 flex-shrink-0', statusStyle.text]"
					/>
					<div>
						<p :class="['font-semibold text-base', statusStyle.text]">
							{{ statusStyle.label }}
						</p>
						<p class="text-sm text-gray-500 mt-0.5">{{ statusStyle.sub }}</p>
					</div>
				</div>

				<!-- ── Progress Bar ── -->
				<div class="mx-4 mt-4">
					<div class="flex items-center justify-between mb-1">
						<span class="text-sm font-medium text-gray-700">
							{{ __("Days selected") }}
						</span>
						<span
							:class="[
								'text-sm font-bold',
								selectedDates.length === 15 ? 'text-green-600' : 'text-blue-600',
							]"
						>
							{{ selectedDates.length }} / 15
						</span>
					</div>
					<div class="h-2 bg-gray-200 rounded-full overflow-hidden">
						<div
							:class="[
								'h-full rounded-full transition-all duration-300',
								selectedDates.length === 15 ? 'bg-green-500' : 'bg-blue-500',
							]"
							:style="{ width: `${(selectedDates.length / 15) * 100}%` }"
						/>
					</div>
				</div>

				<!-- ── Calendar (editable when Draft or no submission) ── -->
				<div v-if="isEditable" class="mx-4 mt-5">
					<!-- Month Navigation -->
					<div class="flex items-center justify-between mb-3">
						<button class="p-2 rounded-lg hover:bg-gray-100 transition-colors" @click="prevMonth">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								class="h-5 w-5 text-gray-600"
								fill="none"
								viewBox="0 0 24 24"
								stroke="currentColor"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M15 19l-7-7 7-7"
								/>
							</svg>
						</button>
						<span class="font-semibold text-gray-800 text-base">
							{{ currentMonthLabel }}
						</span>
						<button class="p-2 rounded-lg hover:bg-gray-100 transition-colors" @click="nextMonth">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								class="h-5 w-5 text-gray-600"
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
						</button>
					</div>

					<!-- Day-of-week headers -->
					<div class="grid grid-cols-7 mb-1">
						<div
							v-for="d in dayHeaders"
							:key="d"
							class="text-center text-xs font-medium text-gray-400 py-1"
						>
							{{ d }}
						</div>
					</div>

					<!-- Day grid -->
					<div class="grid grid-cols-7 gap-y-1">
						<div
							v-for="(day, idx) in calendarDays"
							:key="idx"
							class="flex items-center justify-center"
						>
							<button
								v-if="day"
								:disabled="day.outOfYear || day.weekend"
								:class="[
									'w-9 h-9 rounded-full text-sm font-medium transition-all duration-150',
									day.selected
										? 'bg-blue-500 text-white shadow-sm'
										: day.today
										? 'ring-2 ring-blue-300 text-blue-700'
										: day.outOfYear || day.weekend
										? 'text-gray-300 cursor-not-allowed'
										: 'text-gray-700 hover:bg-gray-100',
								]"
								@click="toggleDate(day.dateStr)"
							>
								{{ day.dayNum }}
							</button>
						</div>
					</div>

					<!-- Warning: at max -->
					<p
						v-if="selectedDates.length >= 15"
						class="mt-3 text-center text-xs text-amber-600 bg-amber-50 rounded-lg py-2"
					>
						{{ __("You've selected 15 days. Deselect a day before adding another.") }}
					</p>
				</div>

				<!-- ── Read-only Date List (Submitted / Approved / Rejected) ── -->
				<div v-else class="mx-4 mt-5">
					<h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
						{{ __("Selected Holiday Dates") }}
					</h3>
					<div class="space-y-2">
						<div
							v-for="(date, idx) in sortedSelectedDates"
							:key="date"
							class="flex items-center gap-3 bg-gray-50 rounded-xl px-4 py-3"
						>
							<span
								class="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0"
							>
								{{ idx + 1 }}
							</span>
							<span class="text-sm font-medium text-gray-800">
								{{ formatDate(date) }}
							</span>
						</div>
					</div>

					<!-- Holiday list link (approved) -->
					<div
						v-if="submission && submission.status === 'Approved' && submission.holiday_list"
						class="mt-4 bg-green-50 rounded-xl px-4 py-3 flex items-center gap-2"
					>
						<span class="text-green-600 text-sm">✓</span>
						<span class="text-sm text-green-700">
							{{ __("Holiday List created:") }}
							<strong>{{ submission.holiday_list }}</strong>
						</span>
					</div>
				</div>

				<!-- ── Selected dates summary (while editing) ── -->
				<div v-if="isEditable && selectedDates.length > 0" class="mx-4 mt-5">
					<h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
						{{ __("Selected Days") }}
					</h3>
					<div class="flex flex-wrap gap-2">
						<span
							v-for="date in sortedSelectedDates"
							:key="date"
							class="flex items-center gap-1 bg-blue-50 text-blue-700 rounded-lg px-2.5 py-1 text-xs font-medium"
						>
							{{ formatDateShort(date) }}
							<button class="ml-0.5 text-blue-400 hover:text-blue-700" @click="toggleDate(date)">
								×
							</button>
						</span>
					</div>
				</div>

				<!-- ── Action Buttons ── -->
				<div v-if="isEditable" class="mx-4 mt-6 flex flex-col gap-3">
					<button
						:disabled="selectedDates.length !== 15 || submitResource.loading"
						:class="[
							'w-full py-3 rounded-xl font-medium text-sm transition-colors',
							selectedDates.length === 15
								? 'bg-blue-500 text-white hover:bg-blue-600'
								: 'bg-gray-200 text-gray-400 cursor-not-allowed',
						]"
						@click="submitHolidays"
					>
						<span v-if="submitResource.loading">{{ __("Submitting…") }}</span>
						<span v-else-if="selectedDates.length === 15">
							{{ __("Submit for Approval") }}
						</span>
						<span v-else> {{ 15 - selectedDates.length }} {{ __("more day(s) needed") }} </span>
					</button>
				</div>
			</div>
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
	toastController,
} from "@ionic/vue"
import { ref, computed, inject, onMounted } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

// ── State ────────────────────────────────────────────────────────────────────

const currentYear = new Date().getFullYear()
const currentViewMonth = ref(dayjs().startOf("month")) // month displayed in calendar
const selectedDates = ref([]) // array of 'YYYY-MM-DD'
const submission = ref(null) // fetched Employee Holiday doc
const initialized = ref(false) // true once the first API load completes

// ── Derived ──────────────────────────────────────────────────────────────────

// Calendar is only shown after the first load AND when the record is Draft (or doesn't exist yet)
const isEditable = computed(
	() => initialized.value && (!submission.value || submission.value.status === "Draft")
)

const sortedSelectedDates = computed(() => [...selectedDates.value].sort())

const statusStyle = computed(() => {
	const s = submission.value?.status
	if (s === "Submitted")
		return {
			bg: "bg-yellow-50",
			text: "text-yellow-700",
			icon: "clock",
			label: __("Pending Approval"),
			sub: __("HR will review your holidays shortly."),
		}
	if (s === "Approved")
		return {
			bg: "bg-green-50",
			text: "text-green-700",
			icon: "check-circle",
			label: __("Approved"),
			sub: __("Your holiday list has been approved and created."),
		}
	if (s === "Rejected")
		return {
			bg: "bg-red-50",
			text: "text-red-700",
			icon: "x-circle",
			label: __("Rejected"),
			sub: __("Your request was rejected. Please contact HR."),
		}
	return {}
})

// ── Calendar helpers ──────────────────────────────────────────────────────────

const dayHeaders = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

const currentMonthLabel = computed(() => currentViewMonth.value.format("MMMM YYYY"))

const calendarDays = computed(() => {
	const monthStart = currentViewMonth.value.startOf("month")
	const monthEnd = currentViewMonth.value.endOf("month")
	const todayStr = dayjs().format("YYYY-MM-DD")

	// Monday = 0 offset; dayjs .day() returns 0=Sun..6=Sat
	const startDow = monthStart.day() // 0=Sun
	const offset = startDow === 0 ? 6 : startDow - 1
	const gridStart = monthStart.subtract(offset, "day")

	// Build 6 rows × 7 cols = 42 cells
	const cells = []
	for (let i = 0; i < 42; i++) {
		const d = gridStart.add(i, "day")
		const dateStr = d.format("YYYY-MM-DD")
		const inCurrentMonth = d.isSame(currentViewMonth.value, "month")
		const outOfYear = d.year() !== currentYear
		const weekend = d.day() === 0 || d.day() === 6

		cells.push({
			dateStr,
			dayNum: d.date(),
			inCurrentMonth,
			outOfYear,
			weekend,
			today: dateStr === todayStr,
			selected: selectedDates.value.includes(dateStr),
			dimmed: !inCurrentMonth,
		})
	}

	// Trim trailing empty rows (all cells of a row outside current month)
	while (cells.length > 35) {
		const lastRow = cells.slice(-7)
		if (lastRow.every((c) => !c.inCurrentMonth)) cells.splice(-7)
		else break
	}

	return cells
})

// ── Actions ───────────────────────────────────────────────────────────────────

function toggleDate(dateStr) {
	if (submission.value && submission.value.status !== "Draft") return

	const idx = selectedDates.value.indexOf(dateStr)
	if (idx !== -1) {
		selectedDates.value.splice(idx, 1)
	} else {
		if (selectedDates.value.length >= 15) return
		selectedDates.value.push(dateStr)
	}
}

function prevMonth() {
	currentViewMonth.value = currentViewMonth.value.subtract(1, "month")
}

function nextMonth() {
	currentViewMonth.value = currentViewMonth.value.add(1, "month")
}

// ── Formatting ────────────────────────────────────────────────────────────────

function formatDate(dateStr) {
	return dayjs(dateStr).format("dddd, MMMM D, YYYY")
}

function formatDateShort(dateStr) {
	return dayjs(dateStr).format("MMM D")
}

// ── API resources ─────────────────────────────────────────────────────────────

const holidayRecord = createResource({
	url: "hrms.api.get_employee_holiday_for_year",
	params: { year: String(currentYear) },
	onSuccess(data) {
		submission.value = data
		if (data && data.holidays) {
			// Frappe can return dates as "2026-05-01 00:00:00" — keep only the date part
			selectedDates.value = data.holidays.map((h) => String(h.date).substring(0, 10))
		} else {
			selectedDates.value = []
		}
		initialized.value = true
	},
	onError() {
		submission.value = null
		initialized.value = true
	},
})

const submitResource = createResource({
	url: "hrms.api.submit_employee_holidays",
	onSuccess(data) {
		submission.value = data
		showToast(__("Holidays submitted for approval!"), "success")
	},
	onError(err) {
		showToast(err.message || __("Failed to submit holidays"), "danger")
	},
})

// ── Handlers ──────────────────────────────────────────────────────────────────

function submitHolidays() {
	if (!submission.value?.name) {
		// Need to save first
		createResource({
			url: "hrms.api.save_employee_holiday_draft",
			onSuccess(data) {
				submission.value = data
				submitResource.submit({ name: data.name })
			},
			onError(err) {
				showToast(err.message || __("Failed to save"), "danger")
			},
		}).submit({
			year: String(currentYear),
			dates: JSON.stringify(selectedDates.value),
		})
	} else {
		submitResource.submit({ name: submission.value.name })
	}
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
	holidayRecord.reload()
})
</script>
