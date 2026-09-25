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

			<!-- Filters: company + timezone -->
			<div v-if="!availResource.loading" class="mx-4 mt-3 flex gap-2 flex-wrap">
				<select
					v-model="companyFilter"
					class="flex-1 min-w-0 border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-300"
					:aria-label="__('Company')"
				>
					<option value="">{{ __("All companies") }}</option>
					<option v-for="c in availableCompanies" :key="c" :value="c">{{ c }}</option>
				</select>
				<select
					v-model="viewerTz"
					class="flex-1 min-w-0 border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-300"
					:aria-label="__('Timezone')"
				>
					<option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">
						{{ tz.label }}
					</option>
				</select>
				<select
					v-model="compareTz"
					class="flex-1 min-w-0 border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-300"
					:aria-label="__('Compare timezone')"
					:title="__('Second timeline axis')"
				>
					<option value="">{{ __("No second axis") }}</option>
					<option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">
						{{ tz.label }}
					</option>
				</select>
			</div>

			<!-- Content -->
			<div v-if="!availResource.loading" class="mx-4 mt-4 pb-10">
				<GridView
					v-if="activeView === 'grid'"
					:dates="gridDates"
					:employees="filteredEmployees"
					:selectedIds="selectedIds"
					@toggleSelect="toggleSelect"
				/>
				<TimelineView
					v-else-if="activeView === 'timeline'"
					:date="selectedDay"
					:employees="filteredEmployees"
					:viewerTz="viewerTz"
					:viewerTzLabel="viewerTzLabel"
					:compareTz="compareTz"
					:compareTzLabel="compareTzLabel"
					:selectedIds="selectedIds"
					@toggleSelect="toggleSelect"
				/>
				<StatusCards
					v-else
					:date="selectedDay"
					:employees="filteredEmployees"
					:viewerTzLabel="viewerTzLabel"
					:selectedIds="selectedIds"
					@toggleSelect="toggleSelect"
				/>
			</div>

			<!-- Selection action bar -->
			<div
				v-if="selectedIds.length"
				class="mx-4 mb-4 p-3 bg-white border rounded-2xl shadow-sm flex items-center gap-3"
			>
				<span class="text-xs font-semibold text-gray-700 whitespace-nowrap">
					{{ selectedIds.length }} {{ __("selected") }}
				</span>
				<button
					class="grow bg-blue-600 active:bg-blue-700 text-white text-sm font-semibold rounded-xl py-2.5 px-3 flex items-center justify-center gap-2"
					@click="openFinder"
				>
					<FeatherIcon name="calendar" class="w-4 h-4" />
					{{ __("Find meeting time") }}
				</button>
				<button
					class="text-xs font-medium text-gray-400 px-1"
					@click="selectedIds = []"
				>
					{{ __("Clear") }}
				</button>
			</div>

			<ion-refresher slot="fixed" @ionRefresh="refresh($event)">
				<ion-refresher-content />
			</ion-refresher>
		</ion-content>

		<!-- Meeting finder popup (plain overlay: bulletproof, no modal machinery) -->
		<div
			v-if="showFinder"
			class="fixed inset-0 z-50 flex flex-col bg-gray-50"
		>
			<div class="flex items-center gap-2 bg-white border-b px-3 py-4 shrink-0">
				<div class="min-w-0 grow text-center">
					<h1 class="text-lg font-semibold text-gray-900">{{ __("Meeting Finder") }}</h1>
				</div>
				<button
					type="button"
					class="text-sm font-semibold text-blue-600 px-2 py-1 shrink-0"
					@click="showFinder = false"
				>
					{{ __("Done") }}
				</button>
			</div>
			<div class="grow overflow-y-auto">
				<MeetingFinderPanel
					:key="finderKey"
					:initialEmployees="finderEmployees"
					:initialFromDate="selectedDay"
					:initialToDate="finderEndDate"
				/>
			</div>
		</div>
	</ion-page>
</template>

<script setup>
import { ref, computed, watch, onMounted, inject } from "vue"
import { FeatherIcon } from "frappe-ui"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonButton,
	IonContent, IonSpinner, IonRefresher, IonRefresherContent,
} from "@ionic/vue"
import { createResource } from "frappe-ui"
import GridView     from "./GridView.vue"
import TimelineView from "./TimelineView.vue"
import StatusCards  from "./StatusCards.vue"
import MeetingFinderPanel from "@/views/meeting/MeetingFinderPanel.vue"
import { getViewerTimezone, getTimezoneAbbr } from "@/utils/timezone.js"

const __ = inject("$translate")
const employee = inject("$employee")

// ── Viewer timezone (selectable; always resets to the user's default on load) ─
const defaultViewerTz = getViewerTimezone() // IANA name  e.g. "America/New_York"
const viewerTz = ref(defaultViewerTz)
const viewerTzLabel = computed(() => getTimezoneAbbr(viewerTz.value))

const BASE_TIMEZONES = [
	"UTC",
	"Pacific/Midway",
	"Pacific/Honolulu",
	"America/Anchorage",
	"America/Los_Angeles",
	"America/Vancouver",
	"America/Phoenix",
	"America/Denver",
	"America/Chicago",
	"America/Mexico_City",
	"America/New_York",
	"America/Toronto",
	"America/Bogota",
	"America/Lima",
	"America/Halifax",
	"America/Caracas",
	"America/Santiago",
	"America/St_Johns",
	"America/Sao_Paulo",
	"America/Buenos_Aires",
	"Atlantic/Azores",
	"Europe/London",
	"Africa/Lagos",
	"Europe/Paris",
	"Europe/Berlin",
	"Europe/Madrid",
	"Europe/Rome",
	"Europe/Athens",
	"Africa/Cairo",
	"Africa/Johannesburg",
	"Europe/Istanbul",
	"Europe/Moscow",
	"Africa/Nairobi",
	"Asia/Baghdad",
	"Asia/Riyadh",
	"Asia/Tehran",
	"Asia/Yerevan",
	"Asia/Baku",
	"Asia/Tbilisi",
	"Asia/Dubai",
	"Asia/Kabul",
	"Asia/Karachi",
	"Asia/Tashkent",
	"Asia/Almaty",
	"Asia/Kolkata",
	"Asia/Colombo",
	"Asia/Kathmandu",
	"Asia/Dhaka",
	"Asia/Bangkok",
	"Asia/Jakarta",
	"Asia/Singapore",
	"Asia/Hong_Kong",
	"Asia/Shanghai",
	"Asia/Taipei",
	"Asia/Manila",
	"Australia/Perth",
	"Asia/Tokyo",
	"Asia/Seoul",
	"Australia/Adelaide",
	"Australia/Sydney",
	"Australia/Brisbane",
	"Pacific/Fiji",
	"Pacific/Auckland",
	"Pacific/Chatham",
]

// System list comes from the Employee Schedule DocType options
// (hrms.api.get_schedule_timezones) so every dropdown stays in sync.
// Falls back to the bundled list if the API is unreachable.
const scheduleTimezones = createResource({
	url: "hrms.api.get_schedule_timezones",
	auto: true,
})

const timezoneOptions = computed(() => {
	const serverList = scheduleTimezones.data?.timezones?.length
		? scheduleTimezones.data.timezones
		: BASE_TIMEZONES
	const zones = serverList.includes(viewerTz.value)
		? serverList
		: [viewerTz.value, ...serverList]
	return zones.map((zone) => ({ value: zone, label: `${getTimezoneAbbr(zone)} · ${zone}` }))
})

// Second timeline axis (compare zone). Defaults to US Eastern unless the
// viewer is already there (then UTC). Never persisted: refresh resets it.
const compareTz = ref(
	defaultViewerTz === "America/New_York" ? "UTC" : "America/New_York"
)
const compareTzLabel = computed(() => getTimezoneAbbr(compareTz.value))

// ── State ──────────────────────────────────────────────────────────────────────
const activeView = ref("timeline")   // "timeline" | "grid" | "cards"

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

// ── People selection for the meeting finder ────────────────────────────────
const selectedIds = ref([]) // employee names
const showFinder = ref(false)
const finderKey = ref(0)

function toggleSelect(employeeId) {
	if (!employeeId) return
	const idx = selectedIds.value.indexOf(employeeId)
	if (idx === -1) selectedIds.value.push(employeeId)
	else selectedIds.value.splice(idx, 1)
}

function openFinder() {
	finderKey.value += 1
	showFinder.value = true
}

// ── Company filter (defaults to the viewer's company; "" = all companies) ────
const companyFilter = ref("")

const availableCompanies = computed(() => {
	const set = new Set()
	for (const row of availResource.data || []) {
		if (row.company) set.add(row.company)
	}
	return [...set].sort()
})

const effectiveCompany = computed(() =>
	availableCompanies.value.includes(companyFilter.value) ? companyFilter.value : ""
)

const filteredEmployees = computed(() => {
	const rows = availResource.data || []
	if (!effectiveCompany.value) return rows
	return rows.filter((r) => (r.company || "") === effectiveCompany.value)
})

const finderEmployees = computed(() => {
	const byId = new Map((availResource.data || []).map((r) => [r.employee, r]))
	return selectedIds.value
		.filter((id) => byId.has(id))
		.map((id) => {
			const r = byId.get(id)
			return { name: id, employee_name: r.employee_name || id, designation: r.designation || "" }
		})
})

const finderEndDate = computed(() => addDays(selectedDay.value, 7))

const views = [
	{ key: "timeline", icon: "clock",  label: __("Timeline") },
	{ key: "grid",     icon: "grid",   label: __("Grid") },
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
		viewer_timezone: viewerTz.value,
	})
}

watch([activeView, weekStart, selectedDay, viewerTz], loadData)

// Keep selection to people present in the loaded data.
// NOTE: this must stay after availResource is defined — the watcher reads it.
watch(
	() => availResource.data,
	(rows) => {
		const ids = new Set((rows || []).map((r) => r.employee))
		selectedIds.value = selectedIds.value.filter((id) => ids.has(id))
	}
)

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

onMounted(() => {
	// Default the company filter to the viewer's own company (resets on refresh)
	const userCompany = employee?.data?.company || ""
	if (userCompany) companyFilter.value = userCompany
	loadData()
})
</script>
