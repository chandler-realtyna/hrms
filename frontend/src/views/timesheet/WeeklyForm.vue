<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="min-h-full bg-gray-50 flex flex-col">
				<header class="flex items-center gap-2 bg-white border-b px-3 py-4 sticky top-0 z-20">
					<Button variant="ghost" class="!pl-0" @click="router.back()">
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</Button>
					<div class="min-w-0 grow">
						<h1 class="text-lg font-semibold text-gray-900">{{ __("Weekly Timesheet") }}</h1>
						<p v-if="timesheet.custom_week_start" class="text-xs text-gray-500">
							{{ formatWeek(timesheet.custom_week_start, timesheet.custom_week_end) }}
						</p>
					</div>
					<span class="text-xs font-medium px-2.5 py-1 rounded-full" :class="statusClass">
						{{ __(timesheet.custom_weekly_status || "Draft") }}
					</span>
				</header>

				<div v-if="loading" class="grow flex items-center justify-center text-sm text-gray-500">
					{{ __("Loading weekly timesheet…") }}
				</div>

				<main v-else class="grow w-full max-w-3xl mx-auto p-4 flex flex-col gap-4">
					<div class="grid grid-cols-2 gap-3">
						<div class="bg-white border rounded-xl p-4">
							<div class="text-xs text-gray-500">{{ __("Total hours") }}</div>
							<div class="text-2xl font-semibold text-gray-900 mt-1">{{ totalHours }}</div>
						</div>
						<router-link
							v-if="!isReadOnly"
							:to="{ name: 'TimesheetTimer' }"
							class="bg-blue-600 text-white rounded-xl p-4 flex items-center justify-between"
						>
							<div>
								<div class="text-xs text-blue-100">{{ __("Track live work") }}</div>
								<div class="font-semibold mt-1">{{ __("Start timer") }}</div>
							</div>
							<FeatherIcon name="play" class="h-5 w-5" />
						</router-link>
						<div v-else class="bg-white border rounded-xl p-4">
							<div class="text-xs text-gray-500">{{ __("Entries") }}</div>
							<div class="text-2xl font-semibold text-gray-900 mt-1">
								{{ timesheet.time_logs?.length || 0 }}
							</div>
						</div>
					</div>

					<div
						v-if="timesheet.custom_weekly_status === 'Correction Required'"
						class="bg-red-50 border border-red-200 rounded-xl p-4"
					>
						<div class="font-semibold text-red-800">{{ __("Correction required") }}</div>
						<p class="text-sm text-red-700 mt-1">{{ timesheet.custom_weekly_return_reason }}</p>
						<p class="text-xs text-red-600 mt-2">
							{{ __("Only returned project entries can be changed.") }}
						</p>
					</div>

					<div v-if="timesheet.project_approvals?.length" class="bg-white border rounded-xl p-4">
						<h2 class="font-semibold text-gray-900 mb-3">{{ __("Project approvals") }}</h2>
						<div class="flex flex-wrap gap-2">
							<span
								v-for="approval in timesheet.project_approvals"
								:key="approval.project"
								class="text-xs px-2.5 py-1.5 rounded-lg border"
								:class="approvalClass(approval.status)"
							>
								{{ projectDisplayName(approval.project) }} · {{ __(approval.status) }}
							</span>
						</div>
					</div>

					<section class="bg-white border rounded-xl p-4">
						<div class="flex items-center justify-between mb-2">
							<h2 class="font-semibold text-gray-900">{{ __("Time entries") }}</h2>
							<span class="text-xs text-gray-500">{{ timesheet.time_logs?.length || 0 }}</span>
						</div>
						<TimeLogsTable
							:timesheet="timesheet"
							:isReadOnly="isReadOnly"
							:weekStart="timesheet.custom_week_start"
							:weekEnd="timesheet.custom_week_end"
							:editableProjects="timesheet.editable_projects || []"
							@addLog="addLog"
							@updateLog="updateLog"
							@deleteLog="deleteLog"
						/>
						<div
							v-if="!timesheet.time_logs?.length"
							class="text-sm text-gray-500 py-4 text-center"
						>
							{{ __("No time entries yet. Add one manually or use the timer.") }}
						</div>
					</section>

					<section class="bg-white border rounded-xl p-4">
						<label class="block text-sm font-medium text-gray-800 mb-2">{{
							__("Weekly note")
						}}</label>
						<textarea
							v-model="timesheet.note"
							:disabled="isReadOnly"
							rows="3"
							class="w-full border rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:bg-gray-50"
							:placeholder="__('Optional note for the week')"
						></textarea>
					</section>
				</main>

				<footer
					v-if="!loading && !isReadOnly"
					class="sticky bottom-0 bg-white border-t p-4 standalone:pb-safe-bottom"
				>
					<div class="max-w-3xl mx-auto flex items-center gap-3">
						<button
							type="button"
							class="min-w-0 grow text-left text-xs"
							:class="autosaveState === 'error' ? 'text-red-600' : 'text-gray-500'"
							:disabled="autosaveState !== 'error'"
							@click="retryAutosave"
						>
							{{ autosaveLabel }}
						</button>
						<Button class="grow py-4" variant="solid" :loading="submitting" @click="submitWeek">
							{{
								timesheet.custom_weekly_status === "Correction Required"
									? __("Resubmit week")
									: __("Submit week")
							}}
						</Button>
					</div>
				</footer>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, call, toast } from "frappe-ui"
import TimeLogsTable from "@/components/TimeLogsTable.vue"
import { useProjectLabels } from "@/composables/useProjectLabels.js"

const { displayName: projectDisplayName, load: loadProjectLabels } = useProjectLabels()

const props = defineProps({ id: { type: String, required: false } })
const __ = inject("$translate")
const dayjs = inject("$dayjs")
const route = useRoute()
const router = useRouter()
const timesheet = ref({ time_logs: [], custom_weekly_status: "Draft" })
const loading = ref(true)
const saving = ref(false)
const submitting = ref(false)
const autosaveState = ref("idle")
const hasUnsavedChanges = ref(false)
const hasEverSaved = ref(false)

// ── Local draft (survives refresh when a save fails) ─────────────────────────
// The server is the source of truth; the draft only ever restores content that
// is strictly newer than the last confirmed server state.
function draftKey() {
	const emp = timesheet.value?.employee || ""
	const week = timesheet.value?.custom_week_start || route.query.week_start || ""
	if (!emp || !week) return ""
	return `hrms_weekly_draft_${emp}_${week}`
}
const lastServerModified = ref("")

function persistDraft() {
	try {
		const key = draftKey()
		if (!key || !hasUnsavedChanges.value) return
		localStorage.setItem(
			key,
			JSON.stringify({
				at: new Date().toISOString(),
				baseModified: lastServerModified.value,
				payload: timesheet.value,
			})
		)
	} catch {
		// storage full/blocked: server remains source of truth
	}
}

function clearPersistedDraft() {
	try {
		const key = draftKey()
		if (key) localStorage.removeItem(key)
	} catch {}
}

function restoreDraftIfNewer() {
	try {
		const key = draftKey()
		if (!key) return false
		const raw = localStorage.getItem(key)
		if (!raw) return false
		const draft = JSON.parse(raw)
		if (!draft?.payload || draft.baseModified !== timesheet.value?.modified) {
			localStorage.removeItem(key)
			return false
		}
		if (!draft.payload?.time_logs?.length && !draft.payload?.note) return false
		timesheet.value = draft.payload
		hasUnsavedChanges.value = true
		recalculate()
		toast({
			title: __("Restored unsaved changes"),
			text: __("Your entries from before the failed save are back. Review and retry."),
			icon: "check",
			iconClasses: "text-green-500",
		})
		return true
	} catch {
		return false
	}
}

// ── Autosave storm gate ──────────────────────────────────────────────────────
// A server rejection (e.g. overlap) is deterministic: retrying the same
// payload hammers the server and spams the error log. Block automatic retries
// until the user makes a structural change (add/edit/delete); note edits and
// manual retry still go through.
const validationBlocked = ref(false)
const blockedRev = ref(-1)
const structRev = ref(0)

let autosaveTimer = null
let saveQueue = Promise.resolve()
let changeRevision = 0
let readyForAutosave = false

const isReadOnly = computed(
	() => !["Draft", "Correction Required"].includes(timesheet.value.custom_weekly_status)
)
const totalHours = computed(() => {
	const total = (timesheet.value.time_logs || []).reduce(
		(sum, row) => sum + Number(row.hours || 0),
		0
	)
	return `${total.toFixed(2)} h`
})
const autosaveLabel = computed(() => {
	if (autosaveState.value === "saving") return __("Saving automatically…")
	if (autosaveState.value === "pending") return __("Changes will be saved automatically")
	if (autosaveState.value === "error") return __("Save failed — tap to retry")
	if (hasEverSaved.value) return __("Saved automatically")
	return __("Changes save automatically")
})
const statusClass = computed(() => {
	const status = timesheet.value.custom_weekly_status
	if (status === "Closed") return "bg-green-100 text-green-700"
	if (status === "Correction Required") return "bg-red-100 text-red-700"
	if (status?.startsWith("Pending")) return "bg-amber-100 text-amber-700"
	return "bg-gray-100 text-gray-700"
})

function formatWeek(start, end) {
	return `${dayjs(start).format("D MMM")} – ${dayjs(end).format("D MMM YYYY")}`
}

function approvalClass(status) {
	if (status === "Approved") return "bg-green-50 text-green-700 border-green-200"
	if (status === "Returned") return "bg-red-50 text-red-700 border-red-200"
	if (status === "HR Review") return "bg-purple-50 text-purple-700 border-purple-200"
	return "bg-amber-50 text-amber-700 border-amber-200"
}

function recalculate() {
	timesheet.value.total_hours = (timesheet.value.time_logs || []).reduce(
		(sum, row) => sum + Number(row.hours || 0),
		0
	)
}

function addLog(log) {
	timesheet.value.time_logs.push(log)
	structRev.value += 1
	recalculate()
	persistDraft()
	scheduleAutosave(0, true)
}

function updateLog(log, index) {
	timesheet.value.time_logs[index] = log
	structRev.value += 1
	recalculate()
	persistDraft()
	scheduleAutosave(0, true)
}

function deleteLog(index) {
	timesheet.value.time_logs.splice(index, 1)
	structRev.value += 1
	recalculate()
	persistDraft()
	scheduleAutosave(0, true)
}

async function load() {
	loading.value = true
	try {
		timesheet.value = await call("hrms.api.weekly_timesheet.get_weekly_timesheet", {
			name: props.id || undefined,
			week_start: props.id ? undefined : route.query.week_start || undefined,
		})
		hasEverSaved.value = Boolean(timesheet.value.name)
		lastServerModified.value = timesheet.value?.modified || ""
		if (restoreDraftIfNewer()) {
			autosaveState.value = "pending"
		}
	} finally {
		readyForAutosave = true
		loading.value = false
	}
}

function scheduleAutosave(delay = 400, force = false) {
	if (!readyForAutosave || isReadOnly.value) return
	if (validationBlocked.value && !force && structRev.value === blockedRev.value) return
	changeRevision += 1
	hasUnsavedChanges.value = true
	autosaveState.value = "pending"
	persistDraft()
	window.clearTimeout(autosaveTimer)
	autosaveTimer = window.setTimeout(() => {
		autosaveTimer = null
		queueAutosave().catch(() => {})
	}, delay)
}

function queueAutosave() {
	const persist = async () => {
		if (!hasUnsavedChanges.value) return timesheet.value.name

		const revisionBeingSaved = changeRevision
		const wasNew = !timesheet.value.name
		hasUnsavedChanges.value = false
		autosaveState.value = "saving"
		saving.value = true

		try {
			const savedTimesheet = await call("hrms.api.weekly_timesheet.save_weekly_timesheet", {
				payload: JSON.stringify(timesheet.value),
			})

			if (changeRevision === revisionBeingSaved) {
				timesheet.value = savedTimesheet
			} else {
				timesheet.value.name = savedTimesheet.name
			}
			hasEverSaved.value = true
			lastServerModified.value = savedTimesheet.modified || lastServerModified.value
			validationBlocked.value = false
			clearPersistedDraft()

			if (wasNew) {
				await router.replace({
					name: "TimesheetDetailView",
					params: { id: savedTimesheet.name },
				})
			}

			autosaveState.value = hasUnsavedChanges.value ? "pending" : "saved"
			return savedTimesheet.name
		} catch (error) {
			hasUnsavedChanges.value = true
			autosaveState.value = "error"
			persistDraft()
			if (error?.messages?.length) {
				// Deterministic server rejection: stop the retry storm until the
				// entries themselves change (note edits alone cannot fix it).
				validationBlocked.value = true
				blockedRev.value = structRev.value
			}
			toast({
				title: __("Could not save changes"),
				text: error?.messages?.[0] || error?.message,
				icon: "alert-circle",
			})
			throw error
		} finally {
			saving.value = false
		}
	}

	saveQueue = saveQueue.then(persist, persist)
	return saveQueue
}

async function flushAutosave() {
	window.clearTimeout(autosaveTimer)
	autosaveTimer = null
	if (hasUnsavedChanges.value) await queueAutosave()
	await saveQueue
	if (hasUnsavedChanges.value) return flushAutosave()
	return timesheet.value.name
}

function retryAutosave() {
	if (autosaveState.value !== "error") return
	validationBlocked.value = false
	scheduleAutosave(0, true)
}

async function submitWeek() {
	if (!timesheet.value.time_logs?.length) {
		toast({ title: __("Add at least one time entry"), icon: "alert-circle" })
		return
	}
	if (!window.confirm(__("Submit this week for project approval?"))) return
	submitting.value = true
	try {
		const name = await flushAutosave()
		timesheet.value = await call("hrms.api.weekly_timesheet.submit_weekly_timesheet", { name })
		toast({ title: __("Week submitted for approval"), icon: "check" })
	} finally {
		submitting.value = false
	}
}

watch(
	() => timesheet.value.note,
	(newValue, oldValue) => {
		if (newValue !== oldValue) scheduleAutosave(700)
	}
)

onMounted(() => { load(); loadProjectLabels() })
</script>
