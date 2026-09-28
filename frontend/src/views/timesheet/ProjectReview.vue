<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-button v-if="detail" @click="detail = null">{{ __("Back") }}</ion-button>
					<ion-back-button v-else default-href="/home" />
				</ion-buttons>
				<ion-title>{{ __("Project Timesheets") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div class="p-4 space-y-4 max-w-3xl mx-auto pb-24">
				<div>
					<h1 class="text-lg font-semibold text-gray-900">{{ __("Review team member hours") }}</h1>
					<p class="text-xs text-gray-500 mt-0.5">
						{{ __("Approve or return submitted hours before HR review") }}
					</p>
				</div>

				<div v-if="loading" class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500">
					{{ __("Loading reviews…") }}
				</div>

				<div v-else-if="!sections.length" class="bg-white border rounded-xl p-10 text-center">
					<FeatherIcon name="check-circle" class="h-8 w-8 text-green-500 mx-auto" />
					<div class="font-medium text-gray-800 mt-3">{{ __("Nothing waiting for review") }}</div>
				</div>

				<!-- List: one row per employee / project / week -->
				<template v-if="!detail">
					<article
						v-for="row in sections"
						:key="row.approval_name"
						class="bg-white border rounded-xl overflow-hidden"
					>
						<button class="w-full text-left p-4" @click="openDetail(row)">
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0">
									<div class="font-semibold text-gray-900 truncate">
										{{ projectLabel(row.project) }}
									</div>
									<div class="text-xs text-gray-500 mt-1">
										{{ row.employee_name }} · {{ formatWeek(row.week_start, row.week_end) }}
									</div>
									<div class="text-xs text-gray-500 mt-0.5">
										{{ formatHours(row.hours) }} · {{ row.log_count }} {{ __("entries") }}
									</div>
								</div>
								<div class="flex flex-col items-end gap-1.5 shrink-0">
									<span class="text-xs px-2 py-0.5 rounded-full" :class="statusClass(row.project_status)">
										{{ __(row.project_status) }}
									</span>
									<span class="text-[11px] text-gray-400">{{ __("HR") }}: {{ __(row.hr_status) }}</span>
								</div>
							</div>
							<p v-if="row.routed_to_hr_reason === 'no_lead'" class="mt-2 text-[11px] text-amber-600">
								{{ __("No Project Lead — routed to HR review") }}
							</p>
							<p v-if="row.routed_to_hr_reason === 'self'" class="mt-2 text-[11px] text-gray-400">
								{{ __("Own section — routed directly to HR") }}
							</p>
							<p v-if="row.return_reason" class="mt-2 text-[11px] text-red-600">
								{{ __("Returned") }}: {{ row.return_reason }}
							</p>
						</button>
						<div v-if="row.actionable" class="px-4 pb-4 flex gap-2">
							<input
								v-model="reasons[row.approval_name]"
								class="min-w-0 flex-1 border rounded-lg px-2.5 py-2 text-xs"
								:placeholder="__('Return reason (to return)')"
							/>
							<Button variant="solid" size="sm" @click="approveRow(row)">
								{{ __("Approve") }}
							</Button>
							<Button variant="subtle" size="sm" @click="returnRow(row)">
								{{ __("Return") }}
							</Button>
						</div>
					</article>
				</template>

				<!-- Detail: time logs for one employee / project / week -->
				<div v-else class="bg-white border rounded-xl overflow-hidden">
					<div class="p-4 border-b">
						<div class="font-semibold text-gray-900">{{ projectLabel(detail.project) }}</div>
						<div class="text-xs text-gray-500 mt-1">
							{{ detail.employee_name }} · {{ formatWeek(detail.week_start, detail.week_end) }}
						</div>
						<div class="mt-2 flex flex-wrap gap-1.5">
							<span class="text-xs px-2 py-0.5 rounded-full" :class="statusClass(detail.project_status)">
								{{ __(detail.project_status) }}
							</span>
							<span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
								{{ __("HR") }}: {{ __(detail.hr_status) }}
							</span>
						</div>
						<p v-if="detail.return_reason" class="mt-2 text-xs text-red-600">
							{{ __("Returned") }}: {{ detail.return_reason }}
						</p>
					</div>
					<div class="divide-y divide-gray-50">
						<div v-for="(log, i) in detail.logs" :key="i" class="px-4 py-3">
							<div class="flex items-baseline justify-between gap-2">
								<span class="text-sm font-medium text-gray-900">{{ log.date }}</span>
								<span class="text-sm font-semibold text-blue-600 tabular-nums">
									{{ formatHours(log.duration) }}
								</span>
							</div>
							<div class="text-xs text-gray-500 mt-0.5">
								{{ log.from_time }}–{{ log.to_time }} · {{ log.activity_type }}
							</div>
							<div v-if="log.description" class="text-xs text-gray-600 mt-0.5">
								{{ log.description }}
							</div>
						</div>
						<div v-if="!detail.logs.length" class="px-4 py-6 text-center text-sm text-gray-400">
							{{ __("No time logs in this section.") }}
						</div>
					</div>
					<div v-if="detail.actionable" class="p-4 border-t flex gap-2">
						<input
							v-model="detailReason"
							class="min-w-0 flex-1 border rounded-lg px-2.5 py-2 text-xs"
							:placeholder="__('Return reason (to return)')"
						/>
						<Button variant="solid" size="sm" @click="approveDetail">
							{{ __("Approve") }}
						</Button>
						<Button variant="subtle" size="sm" @click="returnDetail">
							{{ __("Return") }}
						</Button>
					</div>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from "vue"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonButton, IonBackButton,
} from "@ionic/vue"
import { FeatherIcon, Button, call, toast } from "frappe-ui"

import { formatHours } from "@/utils/formatters.js"
import { useProjectLabels } from "@/composables/useProjectLabels.js"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const { displayName: projectLabel, load: loadProjectLabels } = useProjectLabels()
loadProjectLabels()

const loading = ref(true)
const sections = ref([])
const reasons = reactive({})
const detail = ref(null)
const detailReason = ref("")

function formatWeek(start, end) {
	return `${dayjs(start).format("D MMM")} – ${dayjs(end).format("D MMM YYYY")}`
}

function statusClass(status) {
	if (status === "Approved") return "bg-green-50 text-green-700"
	if (status === "Returned") return "bg-red-50 text-red-700"
	if (status === "HR Review") return "bg-purple-50 text-purple-700"
	return "bg-amber-50 text-amber-700"
}

async function load() {
	loading.value = true
	try {
		sections.value = await call("hrms.api.weekly_timesheet.get_project_review_queue")
	} finally {
		loading.value = false
	}
}

function toastSaved(message) {
	toast({ title: message, icon: "check", iconClasses: "text-green-500" })
}

function toastFailed(error) {
	toast({
		title: __("Action failed"),
		text: error?.messages?.[0] || error?.message,
		icon: "alert-circle",
		iconClasses: "text-red-500",
	})
}

async function openDetail(row) {
	try {
		detailReason.value = ""
		detail.value = await call("hrms.api.weekly_timesheet.get_project_review_detail", {
			project: row.project,
			week_start: row.week_start,
			employee: row.employee,
		})
	} catch (error) {
		toastFailed(error)
	}
}

async function approveRow(row) {
	try {
		await call("hrms.api.weekly_timesheet.approve_project_review", {
			approval_name: row.approval_name,
		})
		toastSaved(__("Section approved — sent to HR review"))
		detail.value = null
		await load()
	} catch (error) {
		toastFailed(error)
	}
}

async function returnRow(row) {
	const reason = (reasons[row.approval_name] || "").trim()
	if (!reason) {
		toast({
			title: __("A return reason is required"),
			icon: "alert-circle",
			iconClasses: "text-amber-500",
		})
		return
	}
	try {
		await call("hrms.api.weekly_timesheet.review_project_approval", {
			approval_name: row.approval_name,
			action: "return",
			reason,
		})
		toastSaved(__("Section returned to the employee"))
		detail.value = null
		await load()
	} catch (error) {
		toastFailed(error)
	}
}

async function approveDetail() {
	if (!detail.value) return
	await approveRow({
		approval_name: detail.value.approval_name,
		project: detail.value.project,
	})
}

async function returnDetail() {
	if (!detail.value) return
	const reason = detailReason.value.trim()
	if (!reason) {
		toast({
			title: __("A return reason is required"),
			icon: "alert-circle",
			iconClasses: "text-amber-500",
		})
		return
	}
	try {
		await call("hrms.api.weekly_timesheet.review_project_approval", {
			approval_name: detail.value.approval_name,
			action: "return",
			reason,
		})
		toastSaved(__("Section returned to the employee"))
		detail.value = null
		await load()
	} catch (error) {
		toastFailed(error)
	}
}

onMounted(load)
</script>
