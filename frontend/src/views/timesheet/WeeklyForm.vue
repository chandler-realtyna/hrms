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

				<div v-else-if="loadError && !timesheet.custom_week_start" class="p-4 text-red-600" role="alert">
					<p>{{ loadError }}</p><Button @click="load">{{ __("Retry") }}</Button>
				</div>
				<main v-else class="grow w-full max-w-3xl mx-auto p-4 flex flex-col gap-4">
					<div v-if="loadError || conflict" class="border-b py-3 text-sm text-amber-600" role="alert">
						<p>{{ conflict ? __("This week changed elsewhere. Your unsaved draft is preserved.") : loadError }}</p>
						<Button v-if="conflict" class="mt-2" @click="reviewLatest">{{ __("Review latest") }}</Button>
						<Button v-if="conflict" class="mt-2 ml-2" @click="downloadDraft">{{ __("Download draft") }}</Button>
						<Button v-else class="mt-2" @click="load">{{ __("Retry") }}</Button>
					</div>
					<p v-if="timesheet.overlap_warnings?.length" class="border-b py-3 text-sm text-amber-600" role="status">
						{{ __("Saved with short overlaps of up to 5 minutes. Your time was not changed.") }}
					</p>
					<section v-if="canWithdraw" class="bg-white border rounded-xl p-4">
						<p class="text-sm text-gray-600 mb-2">{{ __("Need to correct this submission? Reopen the week before HR finalizes it. Saved time stays intact; changed entries require another review.") }}</p>
						<Button variant="subtle" :loading="submitting" :disabled="conflict || saving" @click="withdrawWeek">{{ __("Withdraw submission and edit") }}</Button>
					</section>
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

					<section v-if="timesheet.team_review_blockers?.length" class="border-b py-3">
						<router-link :to="{ name: 'ProjectTimesheets' }" class="font-semibold text-blue-600">
							{{ __("Team reviews outstanding") }} · {{ timesheet.team_review_blockers.length }}
						</router-link>
						<div v-for="item in timesheet.team_review_blockers" :key="`${item.employee_name}|${item.project}`" class="text-sm text-gray-600 mt-1">
							{{ item.employee_name }} · {{ projectDisplayName(item.project) }}
						</div>
					</section>

					<div
						v-if="timesheet.custom_weekly_status === 'Correction Required'"
						class="bg-red-50 border border-red-200 rounded-xl p-4"
					>
						<div class="font-semibold text-red-800">{{ __("Correction required") }}</div>
						<p class="text-sm text-red-700 mt-1">{{ timesheet.custom_weekly_return_reason }}</p>
						<p class="text-xs text-red-600 mt-2">
							{{ __("Only the entries returned for correction can be changed.") }}
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
							:editableEntries="timesheet.editable_entries || []"
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
						<Button class="grow py-4" variant="solid" :loading="submitting" :disabled="conflict" @click="submitWeek">
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
import { computed, inject, onMounted, onUnmounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { IonPage, IonContent, onIonViewWillEnter, onIonViewWillLeave } from "@ionic/vue"
import { Button, FeatherIcon, call, toast } from "frappe-ui"
import TimeLogsTable from "@/components/TimeLogsTable.vue"
import { formatHours } from "@/utils/formatters.js"
import { useProjectLabels } from "@/composables/useProjectLabels.js"

const { displayName: projectDisplayName, load: loadProjectLabels } = useProjectLabels()

const props = defineProps({ id: { type: String, required: false } })
const __ = inject("$translate")
const dayjs = inject("$dayjs")
const route = useRoute()
const router = useRouter()
const timesheet = ref({ time_logs: [], custom_weekly_status: "Draft" })
const loadError = ref(""), conflict = ref(false)
const routeChanging = ref(false)
const socket = inject("$socket")
let active = false, refreshing = false, poller, requestSequence = 0, skipDraftRestore = false
const loading = ref(true)
const saving = ref(false)
const submitting = ref(false)
const canWithdraw = computed(() => Boolean(timesheet.value.name) && Number(timesheet.value.docstatus || 0) === 0 && ["Pending Project Approval", "Pending HR Review"].includes(timesheet.value.custom_weekly_status))

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

function additiveDraft(draft, fresh) {
	// A missing/old version alone must not lock an otherwise identical draft.
	// Rebase only unchanged persisted rows plus new, unnamed additions.
	if (draft?.name !== fresh.name || draft?.employee !== fresh.employee ||
		draft?.custom_week_start !== fresh.custom_week_start ||
		(draft?.note || "") !== (fresh.note || "")) return null
	const rows = new Map((fresh.time_logs || []).map(row => [row.name, row]))
	const seen = new Set(), additions = []
	const sameTime = (a, b) => String(a || "").replace("T", " ").replace(/\.0+$/, "") ===
		String(b || "").replace("T", " ").replace(/\.0+$/, "")
	for (const row of draft.time_logs || []) {
		if (!row.name) { additions.push(row); continue }
		const server = rows.get(row.name)
		if (!server || seen.has(row.name)) return null
		seen.add(row.name)
		if (["project", "activity_type", "description"].some(key => (row[key] || "") !== (server[key] || "")) ||
			!sameTime(row.from_time, server.from_time) || !sameTime(row.to_time, server.to_time) ||
			Math.abs(Number(row.hours || 0) - Number(server.hours || 0)) > 0.00005 ||
			Number(row.is_billable || 0) !== Number(server.is_billable || 0)) return null
	}
	if (seen.size !== rows.size) return null
	return { ...fresh, time_logs: [...fresh.time_logs, ...additions] }
}

function restoreDraftIfNewer() {
	try {
		const key = draftKey()
		if (!key) return false
		const raw = localStorage.getItem(key)
		if (!raw) return false
		const draft = JSON.parse(raw)
		if (!draft?.payload) return false
		if (draft.baseModified !== (timesheet.value?.modified || "")) {
			const rebased = additiveDraft(draft.payload, timesheet.value)
			if (!rebased) { conflict.value = true; return false }
			if (rebased.time_logs.length === timesheet.value.time_logs.length) {
				clearPersistedDraft()
				return false
			}
			draft.payload = rebased
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
	() => routeChanging.value || conflict.value || !["Draft", "Correction Required"].includes(timesheet.value.custom_weekly_status)
)
const totalHours = computed(() => {
	const total = (timesheet.value.time_logs || []).reduce(
		(sum, row) => sum + Number(row.hours || 0),
		0
	)
	return formatHours(total)
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
	if (refreshing || saving.value || submitting.value) return
	refreshing = true
	const sequence = ++requestSequence
	const revisionBefore = changeRevision
	const versionBefore = lastServerModified.value
	const name = props.id, week = route.query.week_start
	let timeout
	try {
		const fresh = await Promise.race([
			call("hrms.api.weekly_timesheet.get_weekly_timesheet", {
				name: name || undefined, week_start: name ? undefined : week || undefined,
			}),
			new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error(__("Could not load this week. Please retry."))), 15000) }),
		])
		if (sequence !== requestSequence || name !== props.id || week !== route.query.week_start ||
			saving.value || versionBefore !== lastServerModified.value) return
		loadError.value = ""
		if (hasUnsavedChanges.value || revisionBefore !== changeRevision) {
			if ((fresh.modified || "") !== lastServerModified.value) conflict.value = true
			persistDraft()
			return
		}
		readyForAutosave = false
		timesheet.value = fresh
		hasEverSaved.value = Boolean(fresh.name)
		lastServerModified.value = fresh.modified || ""
		if (!skipDraftRestore && restoreDraftIfNewer()) autosaveState.value = "pending"
		skipDraftRestore = false
		await Promise.resolve()
	} catch (err) {
		loadError.value = err?.messages?.[0] || err?.message || __("Could not load this week.")
	} finally {
		clearTimeout(timeout)
		readyForAutosave = true
		refreshing = false
		loading.value = false
		if (routeChanging.value) resetRoute()
		else if (hasUnsavedChanges.value && !conflict.value && !validationBlocked.value) scheduleAutosave(0)
	}
}
function reviewLatest() {
	persistDraft()
	if (!window.confirm(__("Your draft remains stored on this device. Display the latest server version without applying that draft?"))) return
	try {
		const key = draftKey(), draft = localStorage.getItem(key)
		if (draft) localStorage.setItem(`${key}_recovery_${Date.now()}`, draft)
		clearPersistedDraft()
	} catch { return }
	hasUnsavedChanges.value = false
	conflict.value = false
	validationBlocked.value = false
	skipDraftRestore = true
	// Keep the conflicting draft, but do not restore it over the new version.
	void load()
}
function downloadDraft() {
	persistDraft()
	const draft = localStorage.getItem(draftKey())
	if (!draft) return
	const url = URL.createObjectURL(new Blob([draft], { type: "application/json" }))
	const link = document.createElement("a")
	link.href = url; link.download = "weekly-timesheet-draft.json"; link.click()
	URL.revokeObjectURL(url)
}
function refreshWhenActive() {
	if (active && document.visibilityState !== "hidden") void load()
}
function enter() {
	active = true
	if (!poller) poller = setInterval(refreshWhenActive, 30000)
	refreshWhenActive()
}
function leave() { active = false; clearInterval(poller); poller = null; persistDraft() }

function scheduleAutosave(delay = 400, force = false) {
	if (!readyForAutosave || isReadOnly.value || conflict.value) return
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
		if (conflict.value) throw new Error(__("Review the latest version before saving."))
		if (!hasUnsavedChanges.value) return timesheet.value.name

		const revisionBeingSaved = changeRevision
		const wasNew = !timesheet.value.name
		hasUnsavedChanges.value = false
		autosaveState.value = "saving"
		saving.value = true

		try {
			const savedTimesheet = await call("hrms.api.weekly_timesheet.save_weekly_timesheet", {
				payload: JSON.stringify(timesheet.value),
				expected_modified: lastServerModified.value,
			})

			if (changeRevision === revisionBeingSaved) {
				timesheet.value = savedTimesheet
			} else {
				timesheet.value.name = savedTimesheet.name
				timesheet.value.modified = savedTimesheet.modified
			}
			hasEverSaved.value = true
			lastServerModified.value = savedTimesheet.modified || lastServerModified.value
			validationBlocked.value = false
			if (!hasUnsavedChanges.value) clearPersistedDraft()
			else persistDraft()

			if (wasNew && !routeChanging.value) {
				await router.replace({
					name: "TimesheetDetailView",
					params: { id: savedTimesheet.name },
				})
			}

			autosaveState.value = hasUnsavedChanges.value ? "pending" : "saved"
			return savedTimesheet.name
		} catch (error) {
			if (error?.exc_type === "TimestampMismatchError" || /changed elsewhere/.test(error?.messages?.[0] || error?.message || "")) conflict.value = true
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
			if (routeChanging.value) resetRoute()
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

async function withdrawWeek() {
	if (!canWithdraw.value || submitting.value || conflict.value) return
	const reason = window.prompt(__("Why are you reopening this week? Saved time and unchanged approvals will be kept."))?.trim()
	if (!reason) return
	submitting.value = true
	try {
		const fresh = await call("hrms.api.weekly_timesheet.reopen_weekly_timesheet", {
			name: timesheet.value.name, expected_modified: lastServerModified.value, reason,
		})
		readyForAutosave = false
		timesheet.value = fresh
		lastServerModified.value = fresh.modified || ""
		hasUnsavedChanges.value = false
		autosaveState.value = "idle"
		clearPersistedDraft()
		await Promise.resolve()
		toast({ title: __("Week reopened. Review your entries and submit again when complete."), icon: "check" })
	} catch (error) {
		toast({ title: __("Could not reopen the week"), text: error?.messages?.[0] || error?.message, icon: "alert-circle" })
	} finally {
		readyForAutosave = true
		submitting.value = false
		if (routeChanging.value) resetRoute()
	}
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
		if (routeChanging.value) resetRoute()
	}
}

watch(
	() => timesheet.value.note,
	(newValue, oldValue) => {
		if (newValue !== oldValue) scheduleAutosave(700)
	}
)

onMounted(() => {
	loadProjectLabels(); enter()
	window.addEventListener("focus", refreshWhenActive)
	window.addEventListener("online", refreshWhenActive)
	document.addEventListener("visibilitychange", refreshWhenActive)
	socket?.on("hrms:week_changed", refreshWhenActive)
	socket?.on("connect", refreshWhenActive)
})
onIonViewWillEnter(enter)
onIonViewWillLeave(leave)
function resetRoute() {
	if (saving.value || submitting.value || refreshing) return
	routeChanging.value = false
	readyForAutosave = false
	timesheet.value = { time_logs: [], custom_weekly_status: "Draft" }
	lastServerModified.value = ""
	hasUnsavedChanges.value = false
	conflict.value = false
	validationBlocked.value = false
	autosaveState.value = "idle"
	loading.value = true
	refreshWhenActive()
}
watch(() => [props.id, route.query.week_start], () => {
	if (props.id && props.id === timesheet.value.name) return
	persistDraft()
	clearTimeout(autosaveTimer)
	requestSequence++
	routeChanging.value = true
	resetRoute()
})
onUnmounted(() => {
	leave(); clearTimeout(autosaveTimer)
	window.removeEventListener("focus", refreshWhenActive)
	window.removeEventListener("online", refreshWhenActive)
	document.removeEventListener("visibilitychange", refreshWhenActive)
	socket?.off("hrms:week_changed", refreshWhenActive)
	socket?.off("connect", refreshWhenActive)
})
</script>
