<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-button v-if="detail" @click="detail = null">{{ __("Back") }}</ion-button>
					<ion-back-button v-else default-href="/home" />
				</ion-buttons>
				<ion-title>{{ __("Team Timesheets") }}</ion-title>
				<ion-buttons slot="end">
					<ion-button :aria-label="__('Refresh')" :title="__('Refresh')" :disabled="loading" @click="load">
						<FeatherIcon name="refresh-cw" class="h-4 w-4" />
					</ion-button>
				</ion-buttons>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div class="p-4 space-y-4 max-w-3xl mx-auto pb-24">
				<div>
					<h1 class="text-lg font-semibold text-gray-900">{{ __("Team Timesheets") }}</h1>
					<div v-if="!detail" class="flex flex-wrap items-center gap-3 mt-3">
						<div class="flex items-center gap-2" role="tablist">
							<Button v-for="item in ['current', 'history']" :key="item" :variant="view === item ? 'solid' : 'subtle'" role="tab" :aria-selected="view === item" @click="view = item">{{ __(item === 'current' ? 'Current' : 'History') }}</Button>
						</div>
						<input v-model="search" type="search" :placeholder="__('Search employee, project or activity')" :aria-label="__('Search entries')" class="flex-1 min-w-0 border rounded px-3 py-2 text-sm" />
					</div>
				</div>

				<p v-if="loadError" role="alert" class="text-red-600">{{ loadError }}</p>
				<div v-if="loading" class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500">
					{{ __("Loading reviews…") }}
				</div>

				<div v-else-if="!orderedSections.length" class="bg-white border rounded-xl p-10 text-center">
					<FeatherIcon name="check-circle" class="h-8 w-8 text-green-500 mx-auto" />
					<div class="font-medium text-gray-800 mt-3">{{ __("Nothing waiting for review") }}</div>
				</div>

				<!-- List: one row per employee / project / week.
				     Hours shown here are scoped to this project only, never the
				     employee's full weekly total. Non-actionable rows (draft,
				     returned, approved) are muted so the pending queue stands out. -->
				<!-- Bulk action: approve every pending section at once. Per-record
				     Approve/Return stays on each card below. -->
				<template v-if="!detail">
					<div class="text-xs text-gray-500">{{ __("{0} of {1} sections", [sections.length, total]) }}</div>
					<div
						v-if="actionableSections.length > 1"
						class="bg-white border rounded-xl p-4 flex items-center justify-between gap-3"
					>
						<div class="text-sm text-gray-700">
							{{ __("{0} to review", [actionableSections.length]) }}
						</div>
						<Button
							variant="solid"
							size="sm"
							:disabled="approvingAll"
							@click="approveAll"
						>
							{{ approvingAll ? __("Approving…") : __("Approve visible") }}
						</Button>
					</div>

					<template v-for="(row, index) in orderedSections" :key="row.approval_name || `${row.project}|${row.week_start}|${row.employee}`">
						<div v-if="view === 'current' && (index === 0 || canApprove(row) !== canApprove(orderedSections[index - 1]))" class="pt-2 text-sm font-semibold text-gray-700">
							{{ canApprove(row) ? __("To review") : __("Waiting on others") }}
						</div>
					<article
						class="border rounded-xl overflow-hidden"
						:class="canApprove(row) ? 'bg-white' : 'bg-gray-50'"
					>
						<button class="w-full text-left p-4" @click="openDetail(row)">
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0">
									<div class="font-semibold text-gray-900 truncate">
										{{ row.project_label || projectLabel(row.project) }}
									</div>
									<div class="text-xs text-gray-500 mt-1">
										{{ row.employee_name }} · {{ formatWeek(row.week_start, row.week_end) }}
									</div>
									<div class="text-xs text-gray-500 mt-0.5">
										{{ __("Hours on this project") }}: {{ formatHours(row.hours) }} · {{ row.log_count }} {{ __("entries") }}
									</div>
									<div v-if="row.modified" class="text-[11px] text-gray-400 mt-0.5">
										{{ __("Updated") }} {{ updatedAgo(row.modified) }}
									</div>
									<div class="text-xs text-gray-500 mt-1">{{ (row.activity_types || []).join(", ") }}</div>
								</div>
								<div class="flex flex-col items-end gap-1.5 shrink-0">
									<span :aria-label="__('Review Status')" class="text-xs px-2 py-0.5 rounded-full" :class="statusClass(row.project_status)">
										{{ projectStatusLabel(row) }}
									</span>
								</div>
							</div>
							<p v-if="row.routed_to_hr_reason === 'no_lead'" class="mt-2 text-[11px] text-amber-600">
								{{ __("No Project Lead, routed to HR review") }}
							</p>
							<p v-if="row.routed_to_hr_reason === 'self'" class="mt-2 text-[11px] text-gray-400">
								{{ __("Own section, routed directly to HR") }}
							</p>
							<p v-if="row.return_reason" class="mt-2 text-[11px] text-red-600">
								{{ __("Returned") }}: {{ row.return_reason }}
							</p>
						</button>
						<p v-if="canApprove(row)" class="px-4 pb-2 text-xs text-gray-600">{{ __("Approve saved entries now. Changes require another review; HR finalizes after the employee submits the week.") }}</p>
						<div v-if="canApprove(row)" class="px-4 pb-4 flex gap-2">
							<input
								v-model="reasons[row.timesheet + '|' + row.project]"
								class="min-w-0 flex-1 border rounded-lg px-2.5 py-2 text-xs"
								:placeholder="__('Return reason')"
							/>
							<Button variant="solid" size="sm" @click="approveRow(row)">
								{{ __("Approve") }}
							</Button>
							<Button variant="subtle" size="sm" @click="returnRow(row)">
								{{ __("Return") }}
							</Button>
						</div>
						<p v-else class="px-4 pb-4 text-xs text-gray-600">{{ reviewHint(row) }}</p>
					</article>
					</template>
					<Button v-if="cursor" :disabled="loading" @click="loadMore">{{ __("Load more") }}</Button>
				</template>

				<!-- Detail: time logs for one employee / project / week -->
				<div v-else class="bg-white border rounded-xl overflow-hidden">
					<div class="p-4 border-b">
						<div class="font-semibold text-gray-900">{{ projectLabel(detail.project) }}</div>
						<div class="text-xs text-gray-500 mt-1">
							{{ detail.employee_name }} · {{ formatWeek(detail.week_start, detail.week_end) }}
						</div>
						<div class="text-xs text-gray-500 mt-0.5">
							{{ __("Hours on this project") }}: {{ formatHours(detailProjectTotal) }} · {{ detail.logs.length }} {{ __("entries") }}
						</div>
						<div class="mt-2 flex flex-wrap gap-1.5">
							<span class="text-xs px-2 py-0.5 rounded-full" :class="statusClass(detail.project_status)">
								{{ __("Review Status") }}: {{ projectStatusLabel(detail) }}
							</span>
							<span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
								{{ __("Week Status") }}: {{ projectStatusLabel({ project_status: detail.hr_status }) }}
							</span>
						</div>
						<p v-if="detail.return_reason" class="mt-2 text-xs text-red-600">
							{{ __("Returned") }}: {{ detail.return_reason }}
						</p>
					</div>
					<div v-if="canApprove(detail)" class="p-4 border-t flex gap-2">
						<input
							v-model="detailReason"
							class="min-w-0 flex-1 border rounded-lg px-2.5 py-2 text-xs"
							:placeholder="__('Return reason')"
						/>
						<Button variant="solid" size="sm" @click="approveDetail">
							{{ __("Approve") }}
						</Button>
						<Button variant="subtle" size="sm" @click="returnDetail">
							{{ __("Return") }}
						</Button>
					</div>
					<div v-else class="p-4 border-b bg-gray-50 flex flex-wrap items-center gap-3">
						<p class="text-xs text-gray-600">{{ reviewHint(detail) }}</p>
					</div>
					<details v-if="detail.hr_exception" class="p-4 border-b">
						<summary class="cursor-pointer text-sm font-medium">{{ __("Exceptional HR actions") }}</summary>
						<p class="mt-3 text-xs text-gray-600">{{ __("Use only when the assigned project reviewer cannot act. A reason is required and recorded in the review history.") }}</p>
						<label class="block mt-3 text-sm">
							<span>{{ __("Intervention reason") }}</span>
							<textarea v-model="exceptionReason" class="mt-1 w-full border rounded-lg p-2" :aria-label="__('Intervention reason')" />
						</label>
						<div class="mt-3 flex flex-wrap gap-2">
							<Button v-if="detail.actionable" :disabled="exceptionBusy || !exceptionReason.trim()" @click="exceptionalReview('approve')">{{ __("Approve on behalf of project reviewer") }}</Button>
							<Button v-if="detail.can_return_entries" :disabled="exceptionBusy || !exceptionReason.trim()" @click="exceptionalReview('return')">{{ __("Return project section for correction") }}</Button>
							<Button v-if="detail.can_reset_review" :disabled="exceptionBusy || !exceptionReason.trim()" @click="exceptionalReview('reset')">{{ __("Revoke approval and request project review") }}</Button>
						</div>
					</details>
					<div class="divide-y divide-gray-50">
						<div v-for="(log, i) in detail.logs" :key="i" class="px-4 py-3">
							<div class="flex items-baseline justify-between gap-2">
								<span class="text-sm font-medium text-gray-900">{{ formatDateFull(log.date) }}</span>
								<span class="text-sm font-semibold text-blue-600 tabular-nums">
									{{ formatHours(log.duration) }}
								</span>
							</div>
							<div class="text-xs text-gray-500 mt-0.5">
								{{ log.from_time }}–{{ log.to_time }}<span v-if="activityLabel(log.activity_type)"> · {{ activityLabel(log.activity_type) }}</span>
							</div>
							<div v-if="log.description" class="text-xs text-gray-600 mt-0.5">
								{{ log.description }}
							</div>
							<p v-if="log.approved" class="mt-1 text-xs text-green-700">{{ __("Approved saved version") }}</p>
							<Button v-else-if="detail.regular_reviewer && detail.can_review_entries && !log.return_reason" variant="solid" size="sm" class="mt-2" @click="approveEntry(log)">
								{{ __("Approve entry") }}
							</Button>
							<p v-if="log.return_reason" class="mt-1 text-xs text-red-600">{{ log.return_reason }}</p>
							<Button v-if="detail.regular_reviewer && detail.can_return_entries" variant="subtle" size="sm" class="mt-2" @click="returnEntry(log)">
								{{ __("Return entry for correction") }}
							</Button>
						</div>
						<div v-if="!detail.logs.length" class="px-4 py-6 text-center text-sm text-gray-400">
							{{ __("No time logs in this section.") }}
						</div>
					</div>

				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, reactive, ref, watch, onUnmounted } from "vue"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonButton, IonBackButton, onIonViewWillEnter,
} from "@ionic/vue"
import { FeatherIcon, Button, call, toast } from "frappe-ui"

import { formatHours } from "@/utils/formatters.js"
import { timeAgo as serverTimeAgo } from "@/utils/serverTime.js"
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
const exceptionReason = ref(""), exceptionBusy = ref(false)
const approvingAll = ref(false)
const search = ref(""), view = ref("current"), total = ref(0), cursor = ref(null), loadError = ref("")
let requestVersion = 0, searchTimer

// Project-scoped total for the open section (sum of its own logs only).
const detailProjectTotal = computed(() =>
	(detail.value?.logs || []).reduce((sum, log) => sum + (Number(log.duration) || 0), 0)
)

function formatWeek(start, end) {
	return `${dayjs(start).format("D MMM")} – ${dayjs(end).format("D MMM YYYY")}`
}

function formatDateFull(date) {
	return dayjs(date).format("ddd, D MMM")
}

// The server stores a literal "Unassigned" default: label it explicitly so it
// never reads as a real activity type.
function activityLabel(activityType) {
	if (!activityType || activityType === "Unassigned") return ""
	return activityType
}

// Server datetimes are EST wall times; the shared helper renders them
// relative to the viewer correctly.
function updatedAgo(value) {
	return serverTimeAgo(dayjs, value)
}

// Preserve the server's queue priority across pages; personal entries stay separate.
const orderedSections = computed(() =>
	(sections.value || []).filter(row => !row.is_own_section)
)

function canApprove(row) { return Boolean(row?.regular_reviewer && row?.actionable) }
function reviewHint(row) {
	if (!row?.regular_reviewer && row?.actionable) return __("Awaiting the assigned project reviewer. Open details for exceptional HR actions.")
	return __(row?.selection_reason || "This section is not ready for approval.")
}
const actionableSections = computed(() => orderedSections.value.filter(canApprove))

// One-click approve for the whole pending queue. Reuses the same
// single-section endpoint as the per-record button, one call per section.
async function approveAll() {
	const rows = actionableSections.value
	if (!rows.length || approvingAll.value) return
	if (!window.confirm(__("Approve all {0} project sections?", [rows.length]))) return
	approvingAll.value = true
	try {
		for (const row of rows) {
			const result = await call("hrms.api.weekly_timesheet.review_saved_project_entries", {
				name: row.timesheet, project: row.project, expected_modified: row.modified,
			})
			for (const sibling of rows) {
				if (sibling.timesheet === row.timesheet) sibling.modified = result.modified
			}
		}
		toastSaved(__("Project sections approved"))
		detail.value = null
		await load()
	} catch (error) {
		toastFailed(error)
		await load()
	} finally {
		approvingAll.value = false
	}
}

function statusClass(status) {
	if (status === "Approved") return "bg-green-50 text-green-700"
	if (status === "Returned") return "bg-red-50 text-red-700"
	if (status === "HR Review") return "bg-purple-50 text-purple-700"
	if (status === "Draft") return "bg-gray-100 text-gray-600"
	return "bg-amber-50 text-amber-700"
}

// Drafts can be returned for correction, but cannot yet be approved.
function projectStatusLabel(row) {
	if (row.project_status === "Draft") return __("Draft")
	if (row.project_status === "Pending") return __("Pending")
	if (row.project_status === "HR Review") return __("HR")
	if (row.project_status === "Pending HR Review") return __("HR review")
	if (row.project_status === "Closed") return __("Final")
	if (row.project_status === "Pending Project Approval") return __("Project review")
	if (row.project_status === "Returned" || row.project_status === "Correction Required") return __("Returned")
	return __(row.project_status)
}

async function load(more = false) {
	const version = ++requestVersion
	loading.value = true
	try {
		const data = await call("hrms.api.weekly_timesheet.get_team_timesheet_sections", {
			view: view.value, cursor: more === true ? cursor.value : null, filters: { search: search.value },
		})
		if (version !== requestVersion) return
		sections.value = more === true ? [...sections.value, ...data.rows] : data.rows
		total.value = data.total; cursor.value = data.next_cursor; loadError.value = ""
	} catch (err) {
		if (version !== requestVersion) return
		if (more === true && err?.exc_type === "TeamCursorResetRequired") {
			cursor.value = null
			toast({ title: __("List updated. Showing the first page."), icon: "refresh-cw" })
			return await load()
		}
		loadError.value = err?.messages?.[0] || err?.message || __("Could not load this page.")
	}
	finally { if (version === requestVersion) loading.value = false }
}
function loadMore() { return load(true) }
watch(view, () => { detail.value = null; load() })
watch(search, () => { clearTimeout(searchTimer); searchTimer = setTimeout(load, 300) })
onUnmounted(() => clearTimeout(searchTimer))

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
		exceptionReason.value = ""
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
	if (!canApprove(row)) return
	try {
		await call("hrms.api.weekly_timesheet.review_saved_project_entries", {
			name: row.timesheet, project: row.project, expected_modified: row.modified,
		})
		toastSaved(__("Project section approved"))
		detail.value = null
		await load()
	} catch (error) {
		toastFailed(error)
	}
}

async function returnRow(row) {
	if (!canApprove(row)) return
	const reason = (reasons[row.timesheet + "|" + row.project] || "").trim()
	if (!reason) {
		toast({
			title: __("A return reason is required"),
			icon: "alert-circle",
			iconClasses: "text-amber-500",
		})
		return
	}
	try {
		await call("hrms.api.weekly_timesheet.review_saved_project_entries", {
			name: row.timesheet, project: row.project, expected_modified: row.modified,
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
	await approveRow(detail.value)
}

async function returnDetail() {
	if (!canApprove(detail.value)) return
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
		await call("hrms.api.weekly_timesheet.review_saved_project_entries", {
			name: detail.value.timesheet, project: detail.value.project, expected_modified: detail.value.modified,
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

async function approveEntry(log) {
	if (!detail.value?.regular_reviewer || !detail.value.can_review_entries) return
	try {
		await call("hrms.api.weekly_timesheet.review_saved_project_entries", {
			name: detail.value.timesheet, project: detail.value.project,
			expected_modified: detail.value.modified, entries: [log.name],
		})
		toastSaved(__("Saved entry approved"))
		await openDetail(detail.value)
		await load()
	} catch (error) { toastFailed(error) }
}

async function returnEntry(log) {
	if (!detail.value?.regular_reviewer || !detail.value.can_return_entries) return
	const reason = window.prompt(__("Correction reason for this time entry"))?.trim()
	if (!reason) return
	try {
		await call("hrms.api.weekly_timesheet.review_saved_project_entries", {
			name: detail.value.timesheet, project: detail.value.project, expected_modified: detail.value.modified, entries: [log.name], reason, action: "return",
		})
		toastSaved(__("Time entry returned for correction"))
		await openDetail(detail.value)
		await load()
	} catch (error) { toastFailed(error) }
}

async function exceptionalReview(action) {
	const section = detail.value, reason = exceptionReason.value.trim()
	if (!section?.hr_exception || !reason || exceptionBusy.value) return
	if (action === "approve" && !section.actionable || action === "return" && !section.can_return_entries || action === "reset" && !section.can_reset_review) return
	if (!["approve", "return", "reset"].includes(action)) return
	exceptionBusy.value = true
	try {
		const method = action === "reset" ? "reset_project_review" : "review_saved_project_entries"
		await call(`hrms.api.weekly_timesheet.${method}`, {
			name: section.timesheet, project: section.project, expected_modified: section.modified,
			reason, ...(action === "reset" ? {} : { action }),
		})
		toastSaved(__("Exceptional HR action recorded"))
		await openDetail(section)
		await load()
	} catch (error) { toastFailed(error) }
	finally { exceptionBusy.value = false }
}

// Reload every time the page is shown (first mount included) so a lead
// returning here always sees the latest employee activity.
onIonViewWillEnter(load)
</script>
