<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="min-h-full bg-gray-50">
				<header class="bg-white border-b px-3 py-4 sticky top-0 z-20 flex items-center gap-2">
					<Button variant="ghost" class="!pl-0" @click="router.back()">
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</Button>
					<div>
						<h1 class="text-lg font-semibold text-gray-900">{{ __("Project Weekly Reports") }}</h1>
						<p class="text-xs text-gray-500">
							{{ __("Review daily totals for projects you manage") }}
						</p>
					</div>
				</header>

				<main class="max-w-6xl mx-auto p-4 md:p-6 flex flex-col gap-4">
					<div
						v-if="loading"
						class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500"
					>
						{{ __("Loading reports…") }}
					</div>
					<div v-else-if="!reports.length" class="bg-white border rounded-xl p-10 text-center">
						<FeatherIcon name="check-circle" class="h-8 w-8 text-green-500 mx-auto" />
						<div class="font-medium text-gray-800 mt-3">
							{{ __("Nothing waiting for review") }}
						</div>
					</div>

					<article
						v-for="report in reports"
						:key="report.name"
						class="bg-white border rounded-xl overflow-hidden"
					>
						<div class="p-4 border-b">
							<div class="font-semibold text-gray-900">{{ report.project }}</div>
							<div class="text-xs text-gray-500 mt-1">
								{{ formatWeek(report.week_start, report.week_end) }}
							</div>
						</div>

						<div class="overflow-x-auto">
							<table class="w-full min-w-[900px] text-sm">
								<thead class="bg-gray-50 text-gray-500">
									<tr>
										<th class="text-left font-medium px-4 py-3">{{ __("Team member") }}</th>
										<th
											v-for="day in report.days"
											:key="day"
											class="text-right font-medium px-3 py-3"
										>
											<div>{{ dayjs(day).format("ddd") }}</div>
											<div class="text-[11px] font-normal">{{ dayjs(day).format("D MMM") }}</div>
										</th>
										<th class="text-right font-medium px-3 py-3">{{ __("Total") }}</th>
										<th class="text-left font-medium px-4 py-3">{{ __("Action") }}</th>
									</tr>
								</thead>
								<tbody class="divide-y">
									<tr v-for="member in report.members" :key="member.approval_name">
										<td class="px-4 py-3 font-medium text-gray-900">{{ member.employee_name }}</td>
										<td
											v-for="(hours, index) in member.daily_hours"
											:key="index"
											class="px-3 py-3 text-right text-gray-700 tabular-nums"
										>
											{{ formatHours(hours) }}
										</td>
										<td class="px-3 py-3 text-right font-semibold text-gray-900 tabular-nums">
											{{ formatHours(member.weekly_total) }}
										</td>
										<td class="px-4 py-3 min-w-[230px]">
											<div v-if="member.status === 'Pending'" class="flex gap-2">
												<input
													v-model="reasons[member.approval_name]"
													class="min-w-0 flex-1 border rounded-lg px-2.5 py-2 text-xs"
													:placeholder="__('Return reason')"
												/>
												<Button variant="subtle" @click="returnMember(member)">{{
													__("Return")
												}}</Button>
											</div>
											<span v-else class="text-xs text-gray-500">{{ __(member.status) }}</span>
										</td>
									</tr>
								</tbody>
							</table>
						</div>

						<div class="p-4 bg-gray-50 flex justify-end">
							<Button variant="solid" @click="approveReport(report)">
								{{ __("Approve project week") }}
							</Button>
						</div>
					</article>
				</main>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, call, toast } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()
const reports = ref([])
const reasons = reactive({})
const loading = ref(true)

function formatWeek(start, end) {
	return `${dayjs(start).format("D MMM")} – ${dayjs(end).format("D MMM YYYY")}`
}

function formatHours(hours) {
	return Number(hours || 0).toFixed(2)
}

async function load() {
	loading.value = true
	try {
		reports.value = await call("hrms.api.weekly_timesheet.get_project_approval_queue")
	} finally {
		loading.value = false
	}
}

async function returnMember(member) {
	const reason = (reasons[member.approval_name] || "").trim()
	if (!reason) {
		toast({ title: __("Add a reason before returning"), icon: "alert-circle" })
		return
	}
	await call("hrms.api.weekly_timesheet.review_project_approval", {
		approval_name: member.approval_name,
		action: "return",
		reason,
	})
	toast({ title: __("Returned for correction"), icon: "check" })
	await load()
}

async function approveReport(report) {
	if (!window.confirm(__("Approve all pending team members in this project week?"))) return
	await call("hrms.api.weekly_timesheet.approve_project_week", {
		project: report.project,
		week_start: report.week_start,
	})
	toast({ title: __("Project week approved"), icon: "check" })
	await load()
}

onMounted(load)
</script>
