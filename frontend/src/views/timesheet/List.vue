<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="min-h-full bg-gray-50">
				<header class="bg-white border-b px-4 py-5 sticky top-0 z-20">
					<div class="max-w-4xl mx-auto flex items-center justify-between gap-3">
						<div>
							<h1 class="text-xl font-semibold text-gray-900">{{ __("Weekly Timesheets") }}</h1>
							<p class="text-xs text-gray-500 mt-1">
								{{ __("Add time anytime. Submit once at the end of the week.") }}
							</p>
						</div>
						<Button variant="solid" @click="router.push({ name: 'TimesheetFormView' })">
							{{ __("Open this week") }}
						</Button>
					</div>
				</header>

				<main class="max-w-4xl mx-auto p-4 md:p-6 flex flex-col gap-5">
					<router-link
						v-if="data.project_approvals?.length"
						:to="{ name: 'TimesheetProjectApprovals' }"
						class="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between"
					>
						<div>
							<div class="font-semibold text-amber-900">{{ __("Project weekly reports") }}</div>
							<div class="text-sm text-amber-700 mt-1">
								{{ __("{0} project report(s) waiting", [data.project_approvals.length]) }}
							</div>
						</div>
						<FeatherIcon name="chevron-right" class="h-5 w-5 text-amber-700" />
					</router-link>

					<section>
						<h2 class="text-sm font-semibold text-gray-700 mb-3">{{ __("Weekly workflow") }}</h2>
						<div
							v-if="loading"
							class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500"
						>
							{{ __("Loading…") }}
						</div>
						<div v-else-if="data.weekly?.length" class="grid md:grid-cols-2 gap-3">
							<router-link
								v-for="doc in data.weekly"
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
											{{ Number(doc.total_hours || 0).toFixed(2) }} {{ __("hours") }}
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
						<div v-else class="bg-white border rounded-xl p-8 text-center">
							<div class="font-medium text-gray-800">{{ __("No weekly timesheet yet") }}</div>
							<p class="text-sm text-gray-500 mt-1">
								{{ __("Open this week to add your first entry.") }}
							</p>
						</div>
					</section>

					<section v-if="data.legacy?.length">
						<h2 class="text-sm font-semibold text-gray-700 mb-3">
							{{ __("Previous daily timesheets") }}
						</h2>
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
										{{ Number(doc.total_hours || 0).toFixed(2) }} {{ __("hours") }}
									</div>
								</div>
								<span class="text-xs text-gray-500">{{ __(doc.status || "Draft") }}</span>
							</router-link>
						</div>
					</section>
				</main>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { inject, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, call } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()
const loading = ref(true)
const data = ref({ weekly: [], legacy: [], project_approvals: [] })

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

onMounted(async () => {
	try {
		data.value = await call("hrms.api.weekly_timesheet.get_my_timesheets")
	} finally {
		loading.value = false
	}
})
</script>
