<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="flex flex-col min-h-full bg-gray-50">
				<!-- Header (no back button: bottom tabs + sidebar own navigation) -->
				<header class="flex items-center bg-white shadow-sm px-4 py-4 sticky top-0 z-10 gap-1">
					<h1 class="text-xl font-semibold text-gray-900">{{ __("Time Tracker") }}</h1>
				</header>

				<!-- Timer display -->
				<div
					class="flex flex-col items-center justify-center py-6 mx-4 mt-4 border-b border-gray-200"
				>
					<div
						class="text-4xl font-mono font-bold tabular-nums"
						:class="isRunning ? 'text-gray-900' : 'text-gray-400'"
					>
						{{ formattedTime }}
					</div>
					<div
						v-if="isRunning"
						class="mt-3 flex max-w-full flex-wrap items-center justify-center gap-x-2 gap-y-1 px-4 text-sm text-green-600 font-medium"
					>
						<span class="h-2 w-2 shrink-0 rounded-full bg-green-500 animate-pulse"></span>
						<span class="shrink-0">{{ __("Recording…") }}</span>
						<span v-if="activeProjectLabel" class="shrink-0 text-gray-300 dark:text-gray-500">·</span>
						<span
							v-if="activeProjectLabel"
							class="min-w-0 max-w-full truncate font-semibold text-gray-800 dark:text-gray-100"
							:title="activeProjectLabel"
						>
							{{ activeProjectLabel }}
						</span>
						<span class="flex shrink-0 items-center gap-1">
						<button
							type="button"
							class="flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Add time')"
							:title="__('Forgot to start earlier? Add minutes')"
							:disabled="controlsDisabled" @click="adjustDir = adjustDir === 1 ? 0 : 1"
						>
							+
						</button>
						<button
							type="button"
							class="flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Remove time')"
							:title="__('Forgot to stop sooner? Remove minutes')"
							:disabled="controlsDisabled" @click="adjustDir = adjustDir === -1 ? 0 : -1"
						>
							−
						</button>
						</span>
					</div>
					<div v-else-if="elapsed > 0" class="mt-3 flex max-w-full flex-wrap items-center justify-center gap-x-2 gap-y-1 px-4 text-sm text-gray-400">
						<span class="shrink-0">{{ isPaused ? __("Paused") : __("Stopped") }}</span>
						<span v-if="activeProjectLabel" class="shrink-0 text-gray-300 dark:text-gray-500">·</span>
						<span v-if="activeProjectLabel" class="min-w-0 max-w-full truncate font-medium text-gray-600 dark:text-gray-300" :title="activeProjectLabel">
							{{ activeProjectLabel }}
						</span>
						<button
							v-if="isPaused"
							type="button"
							class="ml-1 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Add time')"
							:title="__('Forgot to start earlier? Add minutes')"
							:disabled="controlsDisabled" @click="adjustDir = adjustDir === 1 ? 0 : 1"
						>
							+
						</button>
						<button
							v-if="isPaused"
							type="button"
							class="flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Remove time')"
							:title="__('Forgot to stop sooner? Remove minutes')"
							:disabled="controlsDisabled" @click="adjustDir = adjustDir === -1 ? 0 : -1"
						>
							−
						</button>
					</div>
					<div v-else class="mt-3 text-sm text-gray-400">
						{{ __("Press Start to begin tracking") }}
					</div>
					<div v-if="adjustDir !== 0" class="mt-3 flex items-center gap-2">
						<input
							v-model.number="adjustMinutes"
							type="number"
							min="1"
							step="1"
							class="w-20 rounded-lg border border-gray-200 bg-white px-2 py-1 text-center text-sm font-semibold text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
							:aria-label="__('Minutes')"
						/>
						<span class="text-xs text-gray-500">{{ __("min") }}</span>
						<button
							type="button"
							class="rounded-lg bg-blue-600 px-3 py-1 text-xs font-semibold text-white"
							:disabled="controlsDisabled" @click="applyAdjust"
						>
							{{ adjustDir > 0 ? __("Add") : __("Trim") }}
						</button>
						<button
							type="button"
							class="px-1 text-sm text-gray-400"
							@click="adjustDir = 0"
						>
							{{ __("Cancel") }}
						</button>
					</div>
				</div>

				<div class="mx-4 mt-4">
					<div v-if="metadataConflict" class="mb-3 flex flex-wrap items-center gap-2 text-sm text-amber-600" role="alert">
						<span>{{ __("The timer changed elsewhere. Your unsaved description was kept separately.") }}</span>
						<button type="button" class="underline" @click="exportRecovery">{{ __("Download draft") }}</button>
						<button type="button" class="underline" @click="metadataConflict = false">{{ __("Use latest timer") }}</button>
					</div>
					<div v-if="error || !connected" class="mb-3 flex items-center justify-between gap-2 text-sm text-amber-600" role="status">
						<span>{{ error || __("Connecting…") }}</span>
						<button type="button" class="shrink-0 underline" :disabled="isSaving" @click="retry">{{ __("Retry") }}</button>
					</div>
					<div v-if="saveConflicts?.rows?.length" class="mb-4 border-b border-gray-200 pb-4 text-sm text-gray-700" role="alert">
						<p class="mb-2 font-semibold">{{ __("This time overlaps existing entries. Your timer is preserved.") }}</p>
						<p class="mb-2 text-xs text-gray-500">{{ saveConflicts.timezone }}</p>
						<ul class="space-y-2">
							<li v-for="row in saveConflicts.rows" :key="row.name" class="flex flex-wrap items-center justify-between gap-2">
								<span>{{ row.project_name }} · {{ row.from_time }} → {{ row.to_time }}</span>
								<router-link class="shrink-0 text-blue-600 underline" :to="{ path: '/timesheets/' + row.timesheet }">{{ __("Review timesheet") }}</router-link>
								</li>
							</ul>
					</div>
					<div v-if="legacyConflict" class="mb-3 flex items-center justify-between gap-2 text-sm text-amber-600">
						<span>{{ __("A local timer was kept separately; the shared timer was not replaced.") }}</span>
						<button type="button" class="shrink-0 underline" @click="exportRecovery">{{ __("Download draft") }}</button>
					</div>
					<div class="mb-2 text-sm font-semibold text-gray-700">{{ __("Projects") }}</div>
					<div class="flex flex-col gap-2">
						<div v-for="project in timerProjects" :key="project.name" class="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-3">
							<div class="flex min-w-0 flex-1 basis-full sm:basis-0 items-center gap-2">
								<button type="button" class="h-8 w-8 shrink-0 flex items-center justify-center" :disabled="controlsDisabled" :aria-label="isFavorite(project.name) ? __('Remove favorite') : __('Add to favorites')" :title="isFavorite(project.name) ? __('Remove favorite') : __('Add to favorites')" @click="toggleFavorite(project.name)">
									<FeatherIcon name="heart" class="h-4 w-4" :class="isFavorite(project.name) ? 'fill-amber-400 text-amber-500' : 'text-gray-400'" />
								</button>
								<span class="truncate text-sm font-medium text-gray-800" :title="projectDisplayLabel(project)">{{ projectDisplayLabel(project) }}</span>
							</div>
							<div class="shrink-0 text-right leading-tight">
								<div class="font-mono text-xs font-semibold tabular-nums text-gray-700">
									{{ projectFormattedTime(project.name) }}
								</div>
								<div class="text-[10px] font-medium text-gray-400">
									{{ projectStatusLabel(project.name) }}
								</div>
							</div>
							<div class="flex items-center gap-2 shrink-0">
							<button class="shrink-0 rounded px-3 py-2 text-xs font-semibold text-white disabled:opacity-50" :disabled="controlsDisabled" :class="projectButtonClass(project.name)" @click="toggleProjectTimer(project.name)">
								<FeatherIcon :name="projectStatus(project.name) === 'running' ? 'pause' : 'play'" class="h-3 w-3 inline mr-1" />
								{{ projectButtonLabel(project.name) }}
							</button>
							<button class="rounded border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 disabled:opacity-40" :disabled="controlsDisabled || projectSeconds(project.name) <= 0" @click="saveProject(project.name)">
								<FeatherIcon name="save" class="h-3 w-3 inline mr-1" />{{ __("Save") }}
							</button>
							<details v-if="projectSeconds(project.name) > 0" class="relative">
								<summary class="list-none cursor-pointer p-2" :aria-label="__('More actions')" :title="__('More actions')"><FeatherIcon name="more-vertical" class="h-4 w-4 text-gray-500" /></summary>
								<button class="absolute right-0 top-full z-20 border rounded bg-white px-3 py-2 text-xs text-red-600 whitespace-nowrap" :disabled="controlsDisabled" @click="discardProject(project.name)">{{ __("Discard unsaved time") }}</button>
							</details>
							</div>
						</div>
					</div>
				</div>

				<!-- Form fields -->
				<div class="flex flex-col gap-4 p-4 mx-4 mt-3 pb-10">
					<FormField
						fieldtype="Link"
						fieldname="project"
						:label="__('Add project')"
						options="Project"
						linkQuery="hrms.api.search_employee_projects"
						v-model="pickedProject"
					/>
					<div v-if="form.project" class="font-semibold text-sm text-gray-800">{{ activeProjectLabel }}</div>
					<FormField
						v-if="form.project"
						fieldtype="Link"
						fieldname="activity_type"
						:label="__('Activity Type')"
						options="Activity Type"
						v-model="form.activity_type"
						:read-only="controlsDisabled"
						@change="persistState"
					/>
					<FormField
						fieldtype="Small Text"
						v-if="form.project"
						fieldname="description"
						:label="__('Description')"
						v-model="form.description"
						:read-only="controlsDisabled"
						@change="persistState"
					/>
				</div>

			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from "vue"
import { IonPage, IonContent, onIonViewWillEnter, onIonViewWillLeave } from "@ionic/vue"
import { FeatherIcon, call, toast } from "frappe-ui"
import FormField from "@/components/FormField.vue"
import { TIMER_STORAGE_KEY as STORAGE_KEY } from "@/data/session.js"

const __ = inject("$translate")
const employee = inject("$employee")
const socket = inject("$socket")
const FAVORITES_KEY = "hrms_favorite_projects"
const isRunning = ref(false), isPaused = ref(false), pausedSince = ref(null), startTime = ref(null)
const elapsed = ref(0), segments = ref([]), isSaving = ref(false)
const form = ref({ project: "", activity_type: "", description: "" })
const favoriteProjects = ref([]), availableProjects = ref([]), pickedProject = ref("")
const adjustDir = ref(0), adjustMinutes = ref(15)
const connected = ref(false), error = ref(""), initialized = ref(false), revision = ref(-1)
const metadataConflict = ref(false)
const serverError = ref("")
const actionError = ref(null), saveConflicts = ref(null)
const saveWarnings = ref([])
const controlsDisabled = computed(() => isSaving.value || !connected.value || revision.value < 0 || metadataConflict.value)
let clockOffset = 0, ticker, poller, metadataTimer, metadataDirty = false, active = false, loading = false
let pending = null
function stateOwner() { return employee.data?.user_id || employee.data?.name }
function pendingKey() { return "hrms_timer_operation:" + stateOwner() }
function recoveryKey() { return "hrms_timer_recovery:" + stateOwner() }
function localRead(key) { try { return JSON.parse(localStorage.getItem(key) || "null") } catch { return null } }
function localWrite(key, value) { try { value ? localStorage.setItem(key, JSON.stringify(value)) : localStorage.removeItem(key) } catch {} }
function message(err) { return err?.messages?.[0] || err?.message || __("Could not connect. Your time is preserved.") }
function serverNow() { return Date.now() + clockOffset }

function hydrate(state, preserveMetadata = false) {
	if (state.revision < revision.value) return
	if (preserveMetadata && state.revision > revision.value) {
		const recovery = localRead(recoveryKey()) || {}
		localWrite(recoveryKey(), { ...recovery, metadataDraft: { revision: revision.value, form: { ...form.value } } })
		metadataDirty = false
		metadataConflict.value = true
		preserveMetadata = false
		clearTimeout(metadataTimer)
	}
	revision.value = state.revision
	initialized.value = state.initialized
	clockOffset = new Date(state.server_now).getTime() - Date.now()
	const timer = state.timer
	const localForm = form.value
	form.value = preserveMetadata && localForm.project === timer.form.project ? localForm : { ...timer.form }
	startTime.value = timer.startTime
	segments.value = timer.segments || []
	isRunning.value = Boolean(timer.startTime)
	isPaused.value = Boolean(timer.isPaused)
	pausedSince.value = timer.pausedSince
	favoriteProjects.value = (state.favorites || []).map(name => availableProjects.value.find(p => p.name === name) || { name })
	serverError.value = state.last_error || ""
	if (state.saved_timesheets?.length) saveWarnings.value = state.overlap_warnings || []
	error.value = actionError.value?.message || serverError.value
	updateElapsed()
}

async function request(operation) {
	return timedCall("hrms.api.timer_state.apply_action", {
		...operation, payload: JSON.stringify(operation.payload),
	})
}
async function timedCall(method, args) {
	let timeout
	try {
		return await Promise.race([call(method, args), new Promise((_, reject) => {
			timeout = setTimeout(() => reject(new Error(__("Could not connect. Your time is preserved."))), 15000)
		})])
	} finally { clearTimeout(timeout) }
}
async function refresh() {
	if (loading || isSaving.value || !active || document.visibilityState === "hidden") return
	if (!navigator.onLine) { connected.value = false; return }
	loading = true
	try {
		if (pending) {
			const operation = pending
			const state = await request(operation)
			clearActionError(operation)
			pending = null; localWrite(pendingKey(), null)
			hydrate(state, metadataDirty)
		} else {
			hydrate(await timedCall("hrms.api.timer_state.get_state"), metadataDirty)
		}
		connected.value = true
		await migrateLegacy()
	} catch (err) {
		const rejected = Boolean(err?.exc_type || err?.messages?.length)
		if (pending && rejected) {
			actionError.value = { ...pending, message: message(err) }
			pending = null; localWrite(pendingKey(), null)
		}
		connected.value = false
		error.value = message(err)
	} finally { loading = false }
}
async function command(action, payload = {}) {
	if (controlsDisabled.value || pending) return false
	if (metadataDirty && action !== "metadata") {
		if (!await command("metadata", { ...form.value })) return false
	}
	isSaving.value = true
	const operation = { action, expected_revision: revision.value,
		operation_id: crypto.randomUUID(), payload }
	pending = operation
	localWrite(pendingKey(), pending)
	try {
		const state = await request(operation)
		clearActionError(operation)
		pending = null; localWrite(pendingKey(), null)
		metadataDirty = false
		hydrate(state)
		connected.value = true
		return true
	} catch (err) {
		// Transport failures keep exactly the same request for safe retry.
		if (err?.exc_type || err?.messages?.length) {
			actionError.value = { ...operation, message: message(err) }
			pending = null; localWrite(pendingKey(), null)
		}
		error.value = message(err)
		connected.value = false
		return false
	} finally {
		isSaving.value = false
		if (!connected.value && navigator.onLine) void refresh()
	}
}
async function retry() {
	await refresh()
	if (connected.value && actionError.value && !controlsDisabled.value) {
		const operation = actionError.value
		if (operation.action === "save") await saveProject(operation.payload.project)
		else await command(operation.action, operation.payload)
	} else if (connected.value && serverError.value && !controlsDisabled.value) {
		await command("retry_save")
	}
}
function clearActionError(operation) {
	const failed = actionError.value
	if (!failed) return
	if ((failed.action === operation.action && failed.payload.project === operation.payload.project) ||
		(operation.action === "discard" && failed.payload.project === operation.payload.project)) {
		actionError.value = null
		saveConflicts.value = null
	}
}
const legacyConflict = ref(false)
async function migrateLegacy() {
	const old = localRead(STORAGE_KEY)
	if (!old || ![stateOwner(), employee.data?.name].includes(old.owner)) return
	localWrite(recoveryKey(), { timer: old, favorites: localRead(FAVORITES_KEY) || [] })
	if (initialized.value) { legacyConflict.value = true; return }
	const ok = await command("import", { timer: old, favorites: localRead(FAVORITES_KEY) || [] })
	if (ok) {
		localWrite(STORAGE_KEY, null); localWrite(FAVORITES_KEY, null); localWrite(recoveryKey(), null)
	}
}
function exportRecovery() {
	const data = localRead(recoveryKey())
	if (!data) return
	const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }))
	const link = document.createElement("a")
	link.href = url; link.download = "timer-recovery.json"; link.click()
	URL.revokeObjectURL(url)
}
function persistState() {
	metadataDirty = true
	clearTimeout(metadataTimer)
	metadataTimer = setTimeout(() => {
		if (!controlsDisabled.value) void command("metadata", { ...form.value })
	}, 500)
}
async function loadProjects() {
	try {
		const rows = await call("hrms.api.search_employee_projects", {
			doctype: "Project", txt: "", searchfield: "name", start: 0, page_len: 500, filters: {},
		})
		availableProjects.value = (rows || []).map(row => ({ name: row[0] || row.name, label: row[1] || row[0] || row.name }))
		favoriteProjects.value = favoriteProjects.value.map(item => availableProjects.value.find(p => p.name === item.name) || item)
	} catch { availableProjects.value = [] }
}
function isFavorite(project) { return favoriteProjects.value.some(p => p.name === project) }
function toggleFavorite(project) { return command("favorite", { project }) }
function projectDisplayLabel(project) { return project?.label || project?.name || "" }
function projectNameLabel(name) { return projectDisplayLabel(availableProjects.value.find(p => p.name === name) || { name }) }
const activeProjectLabel = computed(() => projectNameLabel(form.value.project))
const timerProjects = computed(() => [...new Set([
	...favoriteProjects.value.map(p => p.name), ...segments.value.map(p => p.project),
	form.value.project, pickedProject.value,
].filter(Boolean))].map(name => availableProjects.value.find(p => p.name === name) || { name }))
function projectSeconds(project) {
	void elapsed.value
	const saved = segments.value.filter(s => s.project === project).reduce((sum, s) => sum + Number(s.seconds || 0), 0)
	return saved + (form.value.project === project && startTime.value
		? Math.max(0, Math.floor((serverNow() - new Date(startTime.value).getTime()) / 1000)) : 0)
}
function formatSeconds(seconds) {
	const n = Math.max(0, Math.floor(seconds))
	return [Math.floor(n / 3600), Math.floor(n % 3600 / 60), n % 60].map(x => String(x).padStart(2, "0")).join(":")
}
const formattedTime = computed(() => formatSeconds(projectSeconds(form.value.project)))
function projectFormattedTime(project) { return formatSeconds(projectSeconds(project)) }
function projectStatus(project) {
	if (form.value.project !== project) return "idle"
	return isRunning.value ? "running" : isPaused.value ? "paused" : "idle"
}
function projectStatusLabel(project) {
	return __(projectStatus(project) === "running" ? "Recording" : projectStatus(project) === "paused" ? "Paused" : projectSeconds(project) > 0 ? "Ready to save" : "Ready")
}
function projectButtonLabel(project) {
	const status = projectStatus(project)
	return __(status === "running" ? "Pause" : status === "paused" ? "Resume" : isRunning.value ? "Switch" : "Start")
}
function projectButtonClass(project) { return projectStatus(project) === "running" ? "bg-amber-500" : "bg-blue-500" }
async function toggleProjectTimer(project) {
	clearTimeout(metadataTimer)
	const status = projectStatus(project)
	return command(status === "running" ? "pause" : status === "paused" ? "resume" : isRunning.value ? "switch" : "start",
		{ ...form.value, project })
}
async function saveProject(project) {
	clearTimeout(metadataTimer)
	saveWarnings.value = []
	if (await command("save", { ...form.value, project })) {
		toast({ title: saveWarnings.value.length ? __("Saved with a short overlap") : __("Time log saved!"),
			text: saveWarnings.value.length ? __("Overlaps of up to 5 minutes were kept without changing your time.") : undefined,
			icon: saveWarnings.value.length ? "alert-circle" : "check" })
	} else if (actionError.value?.action === "save") {
		try { saveConflicts.value = await timedCall("hrms.api.timer_state.get_save_conflicts", { project }) }
		catch { /* The save error and all timer intervals remain visible. */ }
	}
}
function discardProject(project) {
	if (controlsDisabled.value || !window.confirm(__("Discard unsaved time for {0}?", [projectNameLabel(project)]))) return
	return command("discard", { ...form.value, project })
}
async function applyAdjust() {
	if (await command("adjust", { seconds: adjustDir.value * Math.max(1, Math.floor(Number(adjustMinutes.value) || 1)) * 60 }))
		adjustDir.value = 0
}
let baseTitle = "", baseFavicon = ""
function updateElapsed() {
	elapsed.value = segments.value.reduce((sum, s) => sum + Number(s.seconds || 0), 0) +
		(startTime.value ? Math.max(0, Math.floor((serverNow() - new Date(startTime.value).getTime()) / 1000)) : 0)
	if (isRunning.value || isPaused.value) document.title = formattedTime.value + " | " + activeProjectLabel.value
	else restoreTabIndicator()
}
function restoreTabIndicator() {
	if (baseTitle) document.title = baseTitle
	const icon = document.querySelector("link[rel~='icon']")
	if (icon && baseFavicon) icon.href = baseFavicon
}
function offline() { connected.value = false }
function enter() {
	active = true
	if (!poller) poller = setInterval(refresh, 10000)
	void refresh()
}
function leave() {
	active = false
	clearInterval(poller); poller = null
}
onMounted(() => {
	baseTitle = document.title
	baseFavicon = document.querySelector("link[rel~='icon']")?.href || ""
	pending = localRead(pendingKey())
	ticker = setInterval(updateElapsed, 1000)
	void loadProjects()
	window.addEventListener("online", refresh); window.addEventListener("offline", offline)
	window.addEventListener("focus", refresh); document.addEventListener("visibilitychange", refresh)
	socket?.on("hrms:timer_changed", refresh)
	socket?.on("connect", refresh)
	enter()
})
onIonViewWillEnter(enter)
onIonViewWillLeave(leave)
onUnmounted(() => {
	leave(); clearInterval(ticker); clearTimeout(metadataTimer)
	window.removeEventListener("online", refresh); window.removeEventListener("offline", offline)
	window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", refresh)
	socket?.off("hrms:timer_changed", refresh)
	socket?.off("connect", refresh)
	restoreTabIndicator()
})
</script>
