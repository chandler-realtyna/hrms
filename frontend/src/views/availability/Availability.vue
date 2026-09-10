<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/home" /></ion-buttons>
				<ion-title>{{ __("Team Availability") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- View toggle -->
			<div class="mx-4 mt-4 bg-gray-100 rounded-2xl p-1 flex gap-1">
				<button
					v-for="v in views"
					:key="v.key"
					:class="[
						'flex-1 flex items-center justify-center gap-1.5 py-2 px-1 rounded-xl text-xs font-semibold transition-all',
						activeView === v.key
							? 'bg-white text-gray-900 shadow-sm'
							: 'text-gray-500 hover:text-gray-700',
					]"
					@click="activeView = v.key"
				>
					<FeatherIcon :name="v.icon" class="w-3.5 h-3.5 shrink-0" />
					{{ v.label }}
				</button>
			</div>

			<!-- Date / week navigator -->
			<div class="mx-4 mt-3 flex items-center justify-between">
				<button
					class="p-2 rounded-xl hover:bg-gray-100 active:bg-gray-200 transition-colors"
					@click="stepBack"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-gray-600" fill="none"
						viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
				</button>

				<!-- Grid: show week range. Timeline/Cards: show single day -->
				<div class="text-center">
					<p v-if="activeView === 'grid'" class="text-sm font-semibold text-gray-800">
						{{ weekRangeLabel }}
					</p>
					<p v-else class="text-sm font-semibold text-gray-800">{{ dayLabel }}</p>
					<p class="text-xs text-gray-400 mt-0.5">{{ __("Times in") }} {{ viewerTzLabel }}</p>
				</div>

				<button
					class="p-2 rounded-xl hover:bg-gray-100 active:bg-gray-200 transition-colors"
					@click="stepForward"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-gray-600" fill="none"
						viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
					</svg>
				</button>
			</div>

			<!-- Loading -->
			<div v-if="availResource.loading" class="flex items-center justify-center h-48">
				<ion-spinner name="crescent" />
			</div>

			<!-- Content -->
			<div v-else class="mx-4 mt-4 pb-10">
				<GridView
					v-if="activeView === 'grid'"
					:dates="gridDates"
					:employees="availResource.data || []"
				/>
				<TimelineView
					v-else-if="activeView === 'timeline'"
					:date="selectedDay"
					:employees="availResource.data || []"
					:viewerTzLabel="viewerTzLabel"
				/>
				<StatusCards
					v-else
					:date="selectedDay"
					:employees="availResource.data || []"
					:viewerTzLabel="viewerTzLabel"
				/>
			</div>

			<ion-refresher slot="fixed" @ionRefresh="refresh($event)">
				<ion-refresher-content />
			</ion-refresher>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, computed, watch, onMounted, inject } from "vue"
import { FeatherIcon } from "frappe-ui"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton,
	IonContent, IonSpinner, IonRefresher, IonRefresherContent,
} from "@ionic/vue"
import { createResource } from "frappe-ui"
import GridView     from "./GridView.vue"
import TimelineView from "./TimelineView.vue"
import StatusCards  from "./StatusCards.vue"
import { getViewerTimezone, getTimezoneAbbr } from "@/utils/timezone.js"

const __ = inject("$translate")

// ── Viewer timezone ────────────────────────────────────────────────────────────
const viewerTz      = getViewerTimezone()           // IANA name  e.g. "America/New_York"
const viewerTzLabel = getTimezoneAbbr(viewerTz)     // Short abbr e.g. "EST", "CET", "GST"

// ── State ──────────────────────────────────────────────────────────────────────
const activeView = ref("grid")   // "grid" | "timeline" | "cards"

// Base anchor: start-of-week (Monday) for Grid view, or a single day for Timeline/Cards
// Store as ISO string "YYYY-MM-DD"
// Use local date — toISOString() returns UTC which is wrong for non-UTC users.
function localDateStr(d = new Date()) {
	const pad = n => String(n).padStart(2, "0")
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const todayStr = localDateStr()

// Compute the Monday of the current week
function getMondayOf(dateStr) {
	const d = new Date(dateStr + "T12:00:00")
	const day = d.getDay() // 0=Sun, 1=Mon, ..., 6=Sat
	const diff = (day === 0 ? -6 : 1 - day) // shift to Monday
	d.setDate(d.getDate() + diff)
	return d.toISOString().substring(0, 10)
}

const weekStart = ref(getMondayOf(todayStr)) // Monday of displayed week
const selectedDay = ref(todayStr)

const views = [
	{ key: "grid",     icon: "grid",   label: __("Grid") },
	{ key: "timeline", icon: "clock",  label: __("Timeline") },
	{ key: "cards",    icon: "layout", label: __("Cards") },
]

// ── Computed dates ─────────────────────────────────────────────────────────────
const gridDates = computed(() => {
	const dates = []
	const base = new Date(weekStart.value + "T12:00:00")
	for (let i = 0; i < 7; i++) {
		const d = new Date(base)
		d.setDate(base.getDate() + i)
		dates.push(d.toISOString().substring(0, 10))
	}
	return dates
})

const apiStartDate = computed(() =>
	activeView.value === "grid" ? gridDates.value[0] : selectedDay.value
)
const apiEndDate = computed(() =>
	activeView.value === "grid" ? gridDates.value[6] : selectedDay.value
)

// ── Labels ─────────────────────────────────────────────────────────────────────
const weekRangeLabel = computed(() => {
	const first = new Date(gridDates.value[0] + "T12:00:00")
	const last  = new Date(gridDates.value[6] + "T12:00:00")
	const opts  = { month: "short", day: "numeric" }
	if (first.getMonth() === last.getMonth()) {
		return `${first.toLocaleDateString("en-US", opts)} – ${last.getDate()}, ${last.getFullYear()}`
	}
	return `${first.toLocaleDateString("en-US", opts)} – ${last.toLocaleDateString("en-US", opts)}, ${last.getFullYear()}`
})

const dayLabel = computed(() => {
	const d = new Date(selectedDay.value + "T12:00:00")
	return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
})

// ── Navigation ─────────────────────────────────────────────────────────────────
function addDays(dateStr, n) {
	const d = new Date(dateStr + "T12:00:00")
	d.setDate(d.getDate() + n)
	return d.toISOString().substring(0, 10)
}

function stepBack() {
	if (activeView.value === "grid") {
		weekStart.value = addDays(weekStart.value, -7)
	} else {
		selectedDay.value = addDays(selectedDay.value, -1)
	}
}
function stepForward() {
	if (activeView.value === "grid") {
		weekStart.value = addDays(weekStart.value, 7)
	} else {
		selectedDay.value = addDays(selectedDay.value, 1)
	}
}

// ── API ────────────────────────────────────────────────────────────────────────
const availResource = createResource({
	url: "hrms.api.get_team_availability",
	onError() {},
})

function loadData() {
	availResource.submit({
		start_date: apiStartDate.value,
		end_date:   apiEndDate.value,
		viewer_timezone: viewerTz,
	})
}

watch([activeView, weekStart, selectedDay], loadData)

async function refresh(event) {
	loadData()
	// Wait for the resource loading to complete
	const checkDone = setInterval(() => {
		if (!availResource.loading) {
			clearInterval(checkDone)
			event.target.complete()
		}
	}, 100)
}

onMounted(loadData)
</script>
