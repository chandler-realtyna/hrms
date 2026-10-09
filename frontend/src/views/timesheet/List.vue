<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="min-h-full bg-gray-50">
				<header class="bg-white border-b px-4 py-5">
					<div class="max-w-4xl mx-auto">
						<h1 class="text-xl font-semibold text-gray-900">{{ __("My Timesheets") }}</h1>
						<p class="text-xs text-gray-500 mt-1">{{ __("Review your time, then submit your week for approval.") }}</p>
					</div>
				</header>
				<main class="max-w-4xl mx-auto p-4 md:p-6 flex flex-col gap-5">
					<div v-if="loadError" role="alert" class="border rounded-xl p-4 text-sm text-red-600">
						<p>{{ loadError }}</p>
						<Button class="mt-2" variant="subtle" @click="load">{{ __("Retry") }}</Button>
					</div>
					<div v-if="loading" class="text-sm text-gray-500 py-4">{{ __("Loading…") }}</div>
					<section v-else-if="currentWeek" class="bg-white border rounded-xl p-4" :aria-label="__('Current week')">
						<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
							<div class="min-w-0">
								<h2 class="text-sm font-semibold text-gray-900">{{ __("Current week") }}</h2>
								<p class="text-sm text-gray-700 mt-1">{{ formatWeek(currentWeek.custom_week_start, currentWeek.custom_week_end) }}</p>
								<div class="flex flex-wrap items-center gap-2 mt-2">
									<span class="text-sm text-gray-600">{{ formatHours(currentWeek.total_hours) }}</span>
									<span class="text-xs px-2 py-1 rounded-full" :class="statusClass(currentWeek.custom_weekly_status)">{{ __(currentWeek.custom_weekly_status || "Draft") }}</span>
								</div>
							</div>
							<Button variant="solid" class="w-full sm:w-auto shrink-0" @click="openCurrentWeek">{{ currentWeekAction }}</Button>
						</div>
						<p v-if="currentWeek.custom_weekly_return_reason" class="text-xs text-red-600 mt-3">{{ currentWeek.custom_weekly_return_reason }}</p>
					</section>
					<template v-for="group in weekGroups" :key="group.title">
						<section v-if="!loading && group.docs.length">
							<h2 class="text-sm font-semibold text-gray-700 mb-3">{{ __(group.title) }}</h2>
							<div class="grid md:grid-cols-2 gap-3">
							<router-link
								v-for="doc in group.docs"
								:key="doc.name"
								:to="{ name: 'TimesheetDetailView', params: { id: doc.name } }"
								class="bg-white border rounded-xl p-4 hover:border-blue-300 transition-colors"
							>
								<div class="flex items-start justify-between gap-3">
									<div>
										<div class="font-medium text-gray-900">
											{{ formatWeek(doc.start_date, doc.end_date) }}
										</div>
										<div class="text-sm text-gray-500 mt-1">
											{{ formatHours(doc.total_hours) }}
										</div>
									</div>
									<span
										class="text-xs px-2 py-1 rounded-full"
										:class="statusClass(doc.custom_weekly_status)"
									>
										{{ __(doc.custom_weekly_status || "Draft") }}
									</span>
								</div>
								<p
									v-if="doc.custom_weekly_return_reason"
									class="text-xs text-red-600 mt-3 line-clamp-2"
								>
									{{ doc.custom_weekly_return_reason }}
								</p>
							</router-link>
							</div>
						</section>
					</template>
					<router-link v-if="!loading && data.project_approvals?.length" :to="{ name: 'TimesheetProjectApprovals' }" class="border rounded-xl px-4 py-3 text-sm text-gray-700 flex items-center justify-between gap-3">
						<span>{{ __("Project reports to review") }} · {{ data.project_approvals.length }}</span>
						<FeatherIcon name="chevron-right" class="h-4 w-4 shrink-0" />
					</router-link>
					<details class="border rounded-xl bg-white">
						<summary class="cursor-pointer px-4 py-3 text-sm text-gray-600">{{ __("Complete another week") }}</summary>
						<div class="px-4 pb-4">
							<label for="other-week-date" class="block text-xs text-gray-500 mb-2">{{ __("Choose any date in the week you need to complete.") }}</label>
							<div class="flex flex-col sm:flex-row gap-2">
								<input id="other-week-date" v-model="selectedWeekDate" type="date" :max="today" class="w-full sm:max-w-xs border rounded-lg px-3 py-2 text-sm bg-white text-gray-900" />
								<Button variant="subtle" :disabled="!selectedWeekDate" @click="openSelectedWeek">{{ __("Open week") }}</Button>
							</div>
						</div>
					</details>
					<details v-if="!loading && (closedWeeks.length || legacyWeeks.length)" class="border rounded-xl bg-white">
						<summary class="cursor-pointer px-4 py-3 text-sm text-gray-600">{{ __("History") }}</summary>
						<div class="px-4 pb-4 space-y-4">
							<section v-if="closedWeeks.length">
								<h2 class="text-xs font-medium text-gray-500 mb-2">{{ __("Closed weeks") }}</h2>
								<div class="divide-y">
									<router-link v-for="doc in closedWeeks" :key="doc.name" :to="{ name: 'TimesheetDetailView', params: { id: doc.name } }" class="flex flex-wrap items-center justify-between gap-2 py-3 text-sm text-gray-600 hover:text-gray-900">
										<span>{{ formatWeek(doc.start_date, doc.end_date) }}</span>
										<span>{{ formatHours(doc.total_hours) }} · {{ __(doc.custom_weekly_status || "Closed") }}</span>
									</router-link>
								</div>
							</section>
							<section v-if="legacyWeeks.length">
								<h2 class="text-xs font-medium text-gray-500 mb-2">{{ __("Earlier records") }}</h2>
								<p class="text-xs text-gray-500 mb-3">{{ __("Records from the previous timesheet system, grouped by week. Open a week to view its original records.") }}</p>
								<label for="archive-month" class="block text-xs text-gray-500 mb-1">{{ __("Filter by month") }}</label>
								<div class="flex gap-2 mb-3">
									<input id="archive-month" v-model="archiveMonth" type="month" class="border rounded-lg px-3 py-2 text-sm bg-white text-gray-900" />
									<Button v-if="archiveMonth" variant="subtle" @click="archiveMonth = ''">{{ __("Clear") }}</Button>
								</div>
								<p v-if="!filteredLegacyWeeks.length" class="text-xs text-gray-500 py-3">{{ __("No earlier records for this month.") }}</p>
								<details v-for="week in filteredLegacyWeeks" :key="week.key" class="border-b last:border-0">
									<summary class="cursor-pointer flex flex-wrap items-center justify-between gap-2 py-3 text-sm text-gray-600">
										<span>{{ week.start ? formatWeek(week.start, week.end) : __("Undated records") }}</span>
										<span>{{ formatHours(week.hours) }} · {{ __("{0} records", [week.docs.length]) }}</span>
									</summary>
									<div class="divide-y pl-3">
										<router-link v-for="doc in week.docs" :key="doc.name" :to="{ name: 'TimesheetDetailView', params: { id: doc.name } }" class="flex flex-wrap justify-between gap-2 py-3 text-sm text-gray-600 hover:text-gray-900">
											<span>{{ formatWeek(doc.start_date, doc.end_date) || __("Undated record") }}</span>
											<span>{{ formatHours(doc.total_hours) }} · {{ __(doc.status || "Draft") }}</span>
										</router-link>
									</div>
								</details>
							</section>
						</div>
					</details>
				</main>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent, onIonViewWillEnter } from "@ionic/vue"
import { Button, FeatherIcon, call } from "frappe-ui"
import { formatHours } from "@/utils/formatters.js"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()
const loading = ref(true), loadError = ref("")
const data = ref({ weekly: [], legacy: [], project_approvals: [] })
const currentWeek = ref(null)
const archiveMonth = ref("")
const legacyWeeks = computed(() => {
	const groups = new Map()
	for (const doc of data.value.legacy || []) {
		if (!(Number(doc.total_hours) > 0)) continue
		const date = doc.start_date || doc.end_date
		const start = date ? dayjs(date).startOf("day").subtract(dayjs(date).day(), "day") : null
		const key = start ? start.format("YYYY-MM-DD") : "undated"
		if (!groups.has(key)) groups.set(key, { key, start: start?.format("YYYY-MM-DD"), end: start?.add(6, "day").format("YYYY-MM-DD"), hours: 0, docs: [] })
		const group = groups.get(key)
		group.hours += Number(doc.total_hours)
		group.docs.push(doc)
	}
	return [...groups.values()].sort((a, b) => (b.start || "").localeCompare(a.start || ""))
})
const filteredLegacyWeeks = computed(() => archiveMonth.value ? legacyWeeks.value.map(week => {
	const docs = week.docs.filter(doc => [doc.start_date, doc.end_date].some(date => date?.startsWith(archiveMonth.value)))
	return { ...week, docs, hours: docs.reduce((sum, doc) => sum + Number(doc.total_hours), 0) }
}).filter(week => week.docs.length) : legacyWeeks.value)

const today = dayjs().format("YYYY-MM-DD")
const selectedWeekDate = ref(dayjs().subtract(7, "day").format("YYYY-MM-DD"))
const editable = doc => ["Draft", "Correction Required"].includes(doc.custom_weekly_status || "Draft") && Number(doc.docstatus || 0) === 0
const currentWeekAction = computed(() => __(editable(currentWeek.value || {}) ? "Continue this week" : "View this week"))
const otherWeeks = computed(() => (data.value.weekly || []).filter(doc => doc.name !== currentWeek.value?.name))
const closed = doc => doc.custom_weekly_status === "Closed" || Number(doc.docstatus) === 1
const closedWeeks = computed(() => otherWeeks.value.filter(closed))
const weekGroups = computed(() => [
	{ title: "Needs correction", docs: otherWeeks.value.filter(doc => !closed(doc) && doc.custom_weekly_status === "Correction Required") },
	{ title: "Weeks to complete", docs: otherWeeks.value.filter(doc => !closed(doc) && (doc.custom_weekly_status || "Draft") === "Draft") },
	{ title: "Awaiting approval", docs: otherWeeks.value.filter(doc => !closed(doc) && !["Draft", "Correction Required"].includes(doc.custom_weekly_status || "Draft")) },
])

function openCurrentWeek() {
	const week = currentWeek.value
	if (!week) return
	router.push(week.name ? { name: "TimesheetDetailView", params: { id: week.name } } :
		{ name: "TimesheetFormView", query: { week_start: week.custom_week_start } })
}
function openSelectedWeek() {
	if (selectedWeekDate.value) router.push({ name: "TimesheetFormView", query: { week_start: selectedWeekDate.value } })
}
function formatWeek(start, end) {
	if (!start) return ""
	if (!end || start === end) return dayjs(start).format("D MMM YYYY")
	return `${dayjs(start).format("D MMM")} – ${dayjs(end).format("D MMM YYYY")}`
}
function statusClass(status) {
	if (status === "Closed") return "bg-green-100 text-green-700"
	if (status === "Correction Required") return "bg-red-100 text-red-700"
	if (status?.startsWith("Pending")) return "bg-amber-100 text-amber-700"
	return "bg-gray-100 text-gray-700"
}
let fetching = false
async function load() {
	if (fetching) return
	fetching = true; loading.value = true; loadError.value = ""
	try {
		const [list, week] = await Promise.all([
			call("hrms.api.weekly_timesheet.get_my_timesheets", { limit: 100 }),
			call("hrms.api.weekly_timesheet.get_weekly_timesheet"),
		])
		data.value = list; currentWeek.value = week
	} catch (error) {
		loadError.value = error?.messages?.[0] || error?.message || __("Could not load your timesheets. Please retry.")
	} finally { fetching = false; loading.value = false }
}
onMounted(load)
onIonViewWillEnter(load)
</script>
