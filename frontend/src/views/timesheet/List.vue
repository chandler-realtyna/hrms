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
					<details v-if="!loading && (closedWeeks.length || data.legacy?.length)" class="border rounded-xl bg-white">
						<summary class="cursor-pointer px-4 py-3 text-sm text-gray-600">{{ __("History") }} · {{ closedWeeks.length + (data.legacy?.length || 0) }}</summary>
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
							<details v-if="data.legacy?.length">
								<summary class="cursor-pointer text-xs text-gray-500 py-2">{{ __("Previous daily timesheets") }} · {{ data.legacy.length }}</summary>
						<div class="bg-white border rounded-xl divide-y overflow-hidden">
							<router-link
								v-for="doc in data.legacy"
								:key="doc.name"
								:to="{ name: 'TimesheetDetailView', params: { id: doc.name } }"
								class="flex items-center justify-between p-3.5 hover:bg-gray-50"
							>
								<div>
									<div class="text-sm font-medium text-gray-800">
										{{ formatWeek(doc.start_date, doc.end_date) }}
									</div>
									<div class="text-xs text-gray-500 mt-0.5">
										{{ formatHours(doc.total_hours) }}
									</div>
								</div>
								<span class="text-xs text-gray-500">{{ __(doc.status || "Draft") }}</span>
							</router-link>
						</div>

							</details>
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
