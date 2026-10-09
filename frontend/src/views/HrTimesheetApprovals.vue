<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/desk" />
				</ion-buttons>
				<ion-title>{{ __("HR Weekly Timesheet Review") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<main class="mx-auto w-full max-w-5xl space-y-4 p-4 md:p-6">
				<div>
					<h1 class="text-lg font-semibold text-gray-900">{{ __("HR Weekly Timesheet Review") }}</h1>
					<p class="mt-1 text-sm text-gray-500">
						{{ __("Review employee weeks after project approval or direct routing to HR.") }}
					</p>
				</div>

				<div v-if="loading" class="rounded border bg-white p-8 text-center text-sm text-gray-500">
					{{ __("Loading timesheets…") }}
				</div>
				<div v-else-if="error" class="rounded border border-red-200 bg-white p-6 text-sm text-red-700">
					{{ __("You do not have permission to review weekly timesheets.") }}
				</div>
				<div v-else-if="!weeks.length" class="rounded border bg-white p-8 text-center text-sm text-gray-500">
					{{ __("No weekly timesheets are waiting for HR review.") }}
				</div>

				<article v-for="week in weeks" :key="week.name" class="overflow-hidden rounded border bg-white">
					<header class="flex flex-wrap items-start justify-between gap-3 border-b p-4">
						<div>
							<h2 class="font-semibold text-gray-900">{{ week.employee_name }}</h2>
							<p class="mt-1 text-sm text-gray-500">
								{{ week.employee }} · {{ formatWeek(week.week_start, week.week_end) }}
							</p>
						</div>
						<div class="text-right">
							<div class="text-lg font-semibold tabular-nums text-gray-900">{{ formatHours(week.total_hours) }}</div>
							<div class="text-xs text-gray-500">{{ __("Weekly total") }}</div>
						</div>
					</header>

					<div class="divide-y">
						<section v-for="project in week.projects" :key="project.project" class="p-4">
							<div class="flex items-center justify-between gap-3">
								<h3 class="font-medium text-gray-800">{{ project.project }}</h3>
								<span class="text-sm font-medium tabular-nums text-gray-700">
									{{ formatHours(project.total_hours) }}
								</span>
							</div>
							<div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
								<span v-for="(hours, date) in project.daily_hours" :key="date">
									{{ formatDay(date) }}: {{ formatHours(hours) }}
								</span>
								<span v-if="!Object.keys(project.daily_hours).length">{{ __("No logged hours") }}</span>
							</div>
						</section>
					</div>

					<div class="divide-y border-t">
						<div v-for="log in week.time_logs" :key="log.name" class="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
							<div class="min-w-0">
								<div>{{ log.project }} · {{ log.from_time }} - {{ log.to_time }}</div>
								<div class="text-gray-500">{{ log.description }}</div>
							</div>
							<Button variant="subtle" :disabled="Boolean(busy[week.name])" @click="returnEntry(week, log)">{{ __("Return entry") }}</Button>
						</div>
					</div>
					<footer class="flex flex-col gap-3 border-t bg-gray-50 p-4 sm:flex-row">
						<input
							v-model="reasons[week.name]"
							class="min-w-0 flex-1 rounded border border-gray-300 bg-white px-3 py-2 text-sm"
							:placeholder="__('Correction reason')"
							:disabled="Boolean(busy[week.name])"
						/>
						<div class="flex gap-2 sm:shrink-0">
							<Button variant="subtle" theme="red" :disabled="Boolean(busy[week.name])" @click="returnWeek(week)">
								{{ __("Return for correction") }}
							</Button>
							<Button variant="solid" :disabled="Boolean(busy[week.name])" @click="approveWeek(week)">
								{{ __("Approve and close week") }}
							</Button>
						</div>
					</footer>
				</article>
			</main>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { inject, ref } from "vue"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, onIonViewWillEnter,
} from "@ionic/vue"
import { Button, call, toast } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const weeks = ref([])
const reasons = ref({})
const busy = ref({})
const loading = ref(true)
const error = ref(false)

function formatHours(value) {
	return `${Number(value || 0).toFixed(2)} ${__("h")}`
}

function formatWeek(start, end) {
	return `${dayjs(start).format("D MMM")} - ${dayjs(end).format("D MMM YYYY")}`
}

function formatDay(date) {
	return dayjs(date).format("ddd D MMM")
}

async function load() {
	loading.value = true
	error.value = false
	try {
		weeks.value = await call("hrms.api.weekly_timesheet.get_hr_weekly_timesheet_queue")
	} catch {
		error.value = true
	} finally {
		loading.value = false
	}
}

async function returnWeek(week) {
	const reason = (reasons.value[week.name] || "").trim()
	if (!reason) {
		toast({ title: __("A correction reason is required"), icon: "alert-circle" })
		return
	}
	busy.value[week.name] = "return"
	try {
		await call("hrms.api.weekly_timesheet.hr_return_weekly_timesheet", { name: week.name, reason })
		toast({ title: __("Returned for correction"), icon: "check", iconClasses: "text-green-500" })
		await load()
	} catch (err) {
		toast({ title: __("Action failed"), text: err?.messages?.[0] || err?.message, icon: "alert-circle" })
	} finally {
		delete busy.value[week.name]
	}
}

async function returnEntry(week, log) {
	const reason = window.prompt(__("Correction reason for this time entry"))?.trim()
	if (!reason) return
	busy.value[week.name] = "return"
	try {
		await call("hrms.api.weekly_timesheet.return_timesheet_entries", { name: week.name, entries: [log.name], reason, stage: "hr" })
		toast({ title: __("Time entry returned for correction"), icon: "check" })
		await load()
	} catch (err) {
		toast({ title: __("Action failed"), text: err?.messages?.[0] || err?.message, icon: "alert-circle" })
	} finally { delete busy.value[week.name] }
}

async function approveWeek(week) {
	if (!window.confirm(__("Approve and close this employee week?"))) return
	busy.value[week.name] = "approve"
	try {
		await call("hrms.api.weekly_timesheet.hr_close_weekly_timesheet", { name: week.name })
		toast({ title: __("Weekly timesheet approved and closed"), icon: "check", iconClasses: "text-green-500" })
		await load()
	} catch (err) {
		toast({ title: __("Action failed"), text: err?.messages?.[0] || err?.message, icon: "alert-circle" })
	} finally {
		delete busy.value[week.name]
	}
}

onIonViewWillEnter(load)
</script>
