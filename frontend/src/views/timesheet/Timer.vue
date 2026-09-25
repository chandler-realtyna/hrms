<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="flex flex-col min-h-full bg-gray-50">
				<!-- Header -->
				<header class="flex items-center bg-white shadow-sm px-3 py-4 sticky top-0 z-10 gap-1">
					<Button variant="ghost" class="!pl-0 hover:bg-white" @click="router.back()">
						<FeatherIcon name="chevron-left" class="h-5 w-5" />
					</Button>
					<h1 class="text-xl font-semibold text-gray-900">{{ __("Time Tracker") }}</h1>
				</header>

				<!-- Timer display -->
				<div
					class="flex flex-col items-center justify-center py-10 bg-white mx-4 mt-4 rounded-xl shadow-sm border"
				>
					<div
						class="text-6xl font-mono font-bold tracking-widest tabular-nums"
						:class="isRunning ? 'text-gray-900' : 'text-gray-400'"
					>
						{{ formattedTime }}
					</div>
					<div
						v-if="isRunning"
						class="mt-3 flex items-center gap-2 text-sm text-green-600 font-medium"
					>
						<span class="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
						{{ __("Recording…") }}
						<span v-if="activeProjectLabel" class="text-gray-300 dark:text-gray-500">·</span>
						<span
							v-if="activeProjectLabel"
							class="max-w-[240px] truncate font-semibold text-gray-800 dark:text-gray-100"
						>
							{{ activeProjectLabel }}
						</span>
						<button
							type="button"
							class="ml-1 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Add time')"
							:title="__('Forgot to start earlier? Add minutes')"
							@click="adjustDir = adjustDir === 1 ? 0 : 1"
						>
							+
						</button>
						<button
							type="button"
							class="flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Remove time')"
							:title="__('Forgot to stop sooner? Remove minutes')"
							@click="adjustDir = adjustDir === -1 ? 0 : -1"
						>
							−
						</button>
					</div>
					<div v-else-if="elapsed > 0" class="mt-3 flex items-center gap-2 text-sm text-gray-400">
						<span>{{ isPaused ? __("Paused") : __("Stopped") }}</span>
						<span v-if="activeProjectLabel" class="text-gray-300 dark:text-gray-500">·</span>
						<span v-if="activeProjectLabel" class="max-w-[240px] truncate font-medium text-gray-600 dark:text-gray-300">
							{{ activeProjectLabel }}
						</span>
						<button
							v-if="isPaused"
							type="button"
							class="ml-1 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Add time')"
							:title="__('Forgot to start earlier? Add minutes')"
							@click="adjustDir = adjustDir === 1 ? 0 : 1"
						>
							+
						</button>
						<button
							v-if="isPaused"
							type="button"
							class="flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 text-base font-bold leading-none text-gray-500 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300"
							:aria-label="__('Remove time')"
							:title="__('Forgot to stop sooner? Remove minutes')"
							@click="adjustDir = adjustDir === -1 ? 0 : -1"
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
							@click="applyAdjust"
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

				<div v-if="favoriteProjects.length" class="mx-4 mt-3">
					<div class="mb-2 text-sm font-semibold text-gray-700">{{ __("Favorite projects") }}</div>
					<div class="flex flex-col gap-2">
						<div v-for="project in favoriteProjects" :key="project.name" class="flex items-center gap-2 rounded-xl border bg-white px-3 py-2 shadow-sm">
							<button class="flex min-w-0 flex-1 items-center gap-2 text-left" @click="selectProject(project.name)">
								<FeatherIcon name="heart" class="h-4 w-4 fill-amber-400 text-amber-500" />
								<span class="truncate text-sm font-medium text-gray-800">{{ projectDisplayLabel(project) }}</span>
							</button>
							<div class="shrink-0 text-right leading-tight">
								<div class="font-mono text-xs font-semibold tabular-nums text-gray-700">
									{{ projectFormattedTime(project.name) }}
								</div>
								<div class="text-[10px] font-medium text-gray-400">
									{{ projectStatusLabel(project.name) }}
								</div>
							</div>
							<button class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white" :class="projectButtonClass(project.name)" @click="toggleProjectTimer(project.name)">
								{{ projectButtonLabel(project.name) }}
							</button>
						</div>
					</div>
				</div>

				<!-- Form fields -->
				<div class="flex flex-col gap-4 p-4 bg-white mx-4 mt-3 rounded-xl shadow-sm border">
					<FormField
						fieldtype="Link"
						fieldname="project"
						:label="__('Project')"
						options="Project"
						linkQuery="hrms.api.search_employee_projects"
						v-model="form.project"
						:reqd="true"
						@change="persistState"
					/>
					<div v-if="form.project" class="-mt-2 flex items-center gap-2">
						<button
							type="button"
							class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold"
							:class="isFavorite(form.project) ? 'border-amber-300 bg-amber-50 text-amber-600 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-400' : 'border-gray-200 text-gray-500 dark:border-gray-600 dark:text-gray-300'"
							@click="toggleFavorite(form.project)"
							:title="isFavorite(form.project) ? __('Remove favorite') : __('Add to favorites')"
						>
							<FeatherIcon name="heart" class="h-4 w-4" :class="isFavorite(form.project) && 'fill-amber-400 text-amber-500'" />
							{{ isFavorite(form.project) ? __("Favorited") : __("Favorite") }}
						</button>
					</div>
					<FormField
						fieldtype="Link"
						fieldname="activity_type"
						:label="__('Activity Type')"
						options="Activity Type"
						v-model="form.activity_type"
						@change="persistState"
					/>
					<FormField
						fieldtype="Small Text"
						fieldname="description"
						:label="__('Description')"
						v-model="form.description"
						@change="persistState"
					/>
					<p class="-mt-2 text-xs text-gray-500">
						{{ __("For Support projects, include the ticket ID or link.") }}
					</p>
				</div>

				<!-- Action buttons -->
				<div class="px-4 mt-4 pb-10 flex flex-col gap-3">
					<!-- Start button (idle state) -->
					<button
						v-if="!isRunning && !isPaused"
						@click="start"
						class="w-full py-5 rounded-xl bg-green-500 active:bg-green-600 text-white font-semibold text-lg flex items-center justify-center gap-2 shadow-sm transition-colors"
					>
						<FeatherIcon name="play" class="h-5 w-5" />
						{{ __("Start Timer") }}
					</button>
					<button v-if="isRunning" @click="pause" class="w-full rounded-xl bg-amber-500 py-4 text-white font-semibold">
						{{ __("Pause") }}
					</button>

					<!-- Stop & Save button (running state) -->
					<button
						v-if="isRunning || isPaused"
						@click="stop"
						:disabled="isSaving"
						class="w-full py-5 rounded-xl bg-red-500 active:bg-red-600 text-white font-semibold text-lg flex items-center justify-center gap-2 shadow-sm transition-colors disabled:opacity-60"
					>
						<FeatherIcon name="square" class="h-5 w-5" />
						{{ isSaving ? __("Saving…") : __("Stop & Save") }}
					</button>
					<button v-if="isPaused" @click="resume" class="w-full rounded-xl bg-green-500 py-4 text-white font-semibold">
						{{ __("Resume") }}
					</button>

					<!-- Discard (running state) -->
					<button
						v-if="isRunning || isPaused"
						@click="discard"
						class="w-full py-3 text-sm text-red-400 font-medium"
					>
						{{ __("Discard") }}
					</button>
				</div>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"
import { FeatherIcon, Button, call, toast } from "frappe-ui"
import FormField from "@/components/FormField.vue"

const router = useRouter()
const __ = inject("$translate")
const employee = inject("$employee")
const dayjs = inject("$dayjs")

const STORAGE_KEY = "hrms_active_timer"
const FAVORITES_KEY = "hrms_favorite_projects"

const isRunning = ref(false)
const isPaused = ref(false)
const pausedSince = ref(null)
const startTime = ref(null) // dayjs-compatible string
const elapsed = ref(0) // seconds in the current session
const segments = ref([])
const isSaving = ref(false)
const form = ref({ project: "", activity_type: "", description: "" })
const favoriteProjects = ref([])
const availableProjects = ref([])
const longRunningNotified = ref(false)

let ticker = null
let pauseTimeout = null
let longRunningTimeout = null

// ─── Browser tab indicator (Toggl-style) ─────────────────────────────────────
// While the timer runs: "<elapsed> • <project>" in the tab title + red
// recording favicon. Restores both when the timer stops. Reminder value:
// you can see at a glance that a timer is still ticking.

let baseTitle = ""
let baseFavicon = ""
const RECORDING_FAVICON =
	"data:image/svg+xml," +
	encodeURIComponent(
		"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='42' fill='#e5484d'/></svg>"
	)

function compactElapsed(totalSeconds) {
	const s = Math.max(0, Math.floor(totalSeconds || 0))
	if (s < 60) return `${s}s`
	const m = Math.floor(s / 60)
	if (s < 3600) return `${m}:${String(s % 60).padStart(2, "0")}`
	return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`
}

function setRecordingFavicon() {
	try {
		let link = document.querySelector("link[rel~='icon']")
		if (!link) {
			link = document.createElement("link")
			link.rel = "icon"
			document.head.appendChild(link)
		}
		if (!baseFavicon) baseFavicon = link.href || ""
		if (link.href !== RECORDING_FAVICON) link.href = RECORDING_FAVICON
	} catch { /* favicon is best-effort */ }
}

function restoreTabIndicator() {
	try {
		if (baseTitle) document.title = baseTitle
		const link = document.querySelector("link[rel~='icon']")
		if (link && baseFavicon && link.href !== baseFavicon) link.href = baseFavicon
	} catch { /* best-effort */ }
}

function refreshTabIndicator() {
	try {
		const label = activeProjectLabel.value || __("Time Tracker")
		if (isRunning.value) {
			document.title = `${compactElapsed(elapsed.value)} • ${label}`
			setRecordingFavicon()
		} else if (isPaused.value && (elapsed.value > 0 || segments.value.length)) {
			document.title = `⏸ ${compactElapsed(elapsed.value)} • ${label}`
			setRecordingFavicon()
		} else {
			restoreTabIndicator()
		}
	} catch { /* best-effort */ }
}

// ─── Computed ────────────────────────────────────────────────────────────────

const formattedTime = computed(() => {
	// Depend on the ticker so the active project's display updates every second.
	return formatSeconds(projectSeconds(form.value.project))
})

const activeProjectLabel = computed(() => {
	const name = form.value.project
	if (!name) return ""
	const found =
		availableProjects.value.find((item) => item.name === name) ||
		favoriteProjects.value.find((item) => item.name === name)
	if (found) return projectDisplayLabel(found)
	return name
})

// ─── Persistence ─────────────────────────────────────────────────────────────

function persistState() {
	localStorage.setItem(
		STORAGE_KEY,
		JSON.stringify({ startTime: startTime.value, form: form.value, segments: segments.value, isPaused: isPaused.value, pausedSince: pausedSince.value })
	)
}

function clearPersistedState() {
	localStorage.removeItem(STORAGE_KEY)
}

function loadPersistedState() {
	try {
		const raw = localStorage.getItem(STORAGE_KEY)
		if (!raw) return
		const state = JSON.parse(raw)
		segments.value = state.segments || []
		if (!state.startTime && !segments.value.length) return
		startTime.value = state.startTime || null
		form.value = state.form || { project: "", activity_type: "", description: "" }
		isPaused.value = Boolean(state.isPaused)
		pausedSince.value = state.pausedSince || null
		isRunning.value = Boolean(state.startTime) && !isPaused.value
		updateElapsed()
		if (isRunning.value) startTick()
		else if (isPaused.value) schedulePausedSave()
		if (isRunning.value) scheduleLongRunningHint()
	} catch {
		clearPersistedState()
	}
}

// ─── Timer control ───────────────────────────────────────────────────────────

function startTick() {
	clearInterval(ticker)
	ticker = setInterval(() => {
		updateElapsed()
	}, 1000)
}

function updateElapsed() {
	const saved = segments.value.reduce((sum, segment) => sum + Number(segment.seconds || 0), 0)
	const current = startTime.value ? Math.max(0, Math.floor((Date.now() - new Date(startTime.value).getTime()) / 1000)) : 0
	elapsed.value = saved + current
	refreshTabIndicator()
}

function loadFavorites() {
	try { favoriteProjects.value = JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]") } catch { favoriteProjects.value = [] }
}

async function loadProjects() {
	try {
		const rows = await call("hrms.api.search_employee_projects", {
			doctype: "Project", txt: "", searchfield: "name", start: 0, page_len: 500, filters: {},
		})
		availableProjects.value = (rows || []).map((row) => ({ name: row[0] || row.name, label: row[1] || row[0] || row.name }))
		favoriteProjects.value = favoriteProjects.value.map((item) => availableProjects.value.find((project) => project.name === item.name) || item)
	} catch { availableProjects.value = [] }
}

function isFavorite(project) { return favoriteProjects.value.some((item) => item.name === project) }
function toggleFavorite(project) {
	if (!project) return
	if (isFavorite(project)) favoriteProjects.value = favoriteProjects.value.filter((item) => item.name !== project)
	else favoriteProjects.value = [availableProjects.value.find((item) => item.name === project) || { name: project, label: project }, ...favoriteProjects.value]
	localStorage.setItem(FAVORITES_KEY, JSON.stringify(favoriteProjects.value))
}
function selectProject(project) {
	form.value.project = project
	persistState()
}
function projectDisplayLabel(project) {
	if (!project) return ""
	const label = project.label || ""
	const name = project.name || ""
	if (!label) return name
	if (!name || label === name || label.includes(name)) return label
	return `${label} : ${name}`
}
function startProject(project) {
	if (isRunning.value && form.value.project !== project) pause()
	form.value.project = project
	if (!isRunning.value) resume()
}
function projectStatus(project) {
	if (form.value.project !== project || (!isRunning.value && !isPaused.value)) return "idle"
	return isRunning.value ? "running" : "paused"
}
function projectSeconds(project) {
	void elapsed.value
	const saved = segments.value
		.filter((segment) => segment.project === project)
		.reduce((sum, segment) => sum + Number(segment.seconds || 0), 0)
	if (form.value.project !== project || !startTime.value) return saved
	return saved + Math.max(0, Math.floor((Date.now() - new Date(startTime.value).getTime()) / 1000))
}
function formatSeconds(totalSeconds) {
	const h = Math.floor(totalSeconds / 3600)
		.toString()
		.padStart(2, "0")
	const m = Math.floor((totalSeconds % 3600) / 60)
		.toString()
		.padStart(2, "0")
	const s = (totalSeconds % 60).toString().padStart(2, "0")
	return `${h}:${m}:${s}`
}
function projectFormattedTime(project) {
	return formatSeconds(projectSeconds(project))
}
function projectStatusLabel(project) {
	const status = projectStatus(project)
	if (status === "running") return __("Recording")
	if (status === "paused") return __("Paused")
	if (projectSeconds(project) > 0) return __("Ready to save")
	return __("Ready")
}
function projectButtonLabel(project) {
	const status = projectStatus(project)
	if (status === "running") return __("Pause")
	if (status === "paused") return __("Resume")
	return isRunning.value ? __("Switch") : __("Start")
}
function projectButtonClass(project) {
	const status = projectStatus(project)
	if (status === "running") return "bg-amber-500"
	if (status === "paused") return "bg-green-500"
	return "bg-blue-500"
}
function toggleProjectTimer(project) {
	const status = projectStatus(project)
	if (status === "running") return pause()
	if (status === "paused") return resume()
	startProject(project)
}

// ─── Manual time adjustment (± minutes, e.g. forgot to start/stop) ──────────
// Adjustments apply to the ACTIVE project only and are baked into segments /
// startTime, so they persist and are saved like normally tracked time.
const adjustDir = ref(0) // 0 = hidden, 1 = add, -1 = trim
const adjustMinutes = ref(15)

function activeProjectSegments() {
	return segments.value.filter((segment) => segment.project === form.value.project)
}

function addTime(totalSeconds) {
	if (startTime.value) {
		startTime.value = new Date(new Date(startTime.value).getTime() - totalSeconds * 1000).toISOString()
	} else {
		const mine = activeProjectSegments()
		if (!mine.length) {
			toast({ title: __("Nothing to adjust yet"), icon: "alert-circle", iconClasses: "text-amber-500" })
			return false
		}
		const last = mine[mine.length - 1]
		last.from = new Date(new Date(last.from).getTime() - totalSeconds * 1000).toISOString()
		last.seconds = Number(last.seconds || 0) + totalSeconds
	}
	updateElapsed()
	persistState()
	return true
}

function trimTime(totalSeconds) {
	let remaining = totalSeconds
	if (startTime.value) {
		const current = Math.max(0, Math.floor((Date.now() - new Date(startTime.value).getTime()) / 1000))
		const take = Math.min(current, remaining)
		startTime.value = new Date(new Date(startTime.value).getTime() + take * 1000).toISOString()
		remaining -= take
	}
	const mine = activeProjectSegments()
	for (let i = mine.length - 1; i >= 0 && remaining > 0; i--) {
		const segment = mine[i]
		const take = Math.min(Number(segment.seconds || 0), remaining)
		segment.seconds = Number(segment.seconds || 0) - take
		segment.to = new Date(new Date(segment.to).getTime() - take * 1000).toISOString()
		remaining -= take
		if (Number(segment.seconds) <= 0) {
			segments.value.splice(segments.value.indexOf(segment), 1)
		}
	}
	updateElapsed()
	persistState()
	if (remaining > 0) {
		toast({ title: __("Trimmed down to zero"), icon: "alert-circle", iconClasses: "text-amber-500" })
	}
	return true
}

function applyAdjust() {
	const minutes = Math.max(1, Math.floor(Number(adjustMinutes.value) || 0))
	adjustMinutes.value = minutes
	const ok = adjustDir.value > 0 ? addTime(minutes * 60) : trimTime(minutes * 60)
	if (ok) {
		toast({
			title:
				adjustDir.value > 0
					? __("Added {0} min", [minutes])
					: __("Trimmed {0} min", [minutes]),
			icon: "check",
			iconClasses: "text-green-500",
		})
		adjustDir.value = 0
	}
}

function pushCurrentSegment() {
	if (!startTime.value) return
	const seconds = Math.max(0, Math.floor((Date.now() - new Date(startTime.value).getTime()) / 1000))
	if (seconds) segments.value.push({ from: startTime.value, to: new Date().toISOString(), seconds, ...form.value })
	startTime.value = null
}

function start() {
	if (!form.value.project) {
		toast({
			title: __("Select a project before starting the timer"),
			icon: "alert-circle",
			iconClasses: "text-red-500",
		})
		return
	}
	segments.value = []
	elapsed.value = 0
	isPaused.value = false
	startTime.value = new Date().toISOString()
	longRunningNotified.value = false
	isRunning.value = true
	startTick()
	scheduleLongRunningHint()
	persistState()
	updateElapsed()
}

function pause() {
	if (!isRunning.value) return
	pushCurrentSegment()
	clearInterval(ticker)
	ticker = null
	clearTimeout(longRunningTimeout)
	isRunning.value = false
	isPaused.value = true
	pausedSince.value = new Date().toISOString()
	updateElapsed()
	refreshTabIndicator()
	persistState()
	schedulePausedSave()
}

function schedulePausedSave() {
	clearTimeout(pauseTimeout)
	if (!isPaused.value || !pausedSince.value) return
	const remaining = Math.max(0, 2 * 60 * 60 * 1000 - (Date.now() - new Date(pausedSince.value).getTime()))
	pauseTimeout = setTimeout(() => {
		if (isPaused.value) stop()
	}, remaining)
}

function scheduleLongRunningHint() {
	clearTimeout(longRunningTimeout)
	if (!isRunning.value || !startTime.value || longRunningNotified.value) return
	const remaining = Math.max(0, 2 * 60 * 60 * 1000 - (Date.now() - new Date(startTime.value).getTime()))
	longRunningTimeout = setTimeout(async () => {
		if (!isRunning.value || longRunningNotified.value) return
		try {
			await call("hrms.api.notify_long_running_timer", { employee: employee.data.name, project: form.value.project, started_at: startTime.value })
			longRunningNotified.value = true
			toast({ title: __("This timer has been running for over two hours. You may have forgotten to save it."), icon: "alert-circle", iconClasses: "text-amber-500" })
		} catch { /* keep timer usable if mail is unavailable */ }
	}, remaining)
}

function resume() {
	if (!form.value.project) return start()
	startTime.value = new Date().toISOString()
	isRunning.value = true
	isPaused.value = false
	pausedSince.value = null
	clearTimeout(pauseTimeout)
	clearTimeout(longRunningTimeout)
	startTick()
	scheduleLongRunningHint()
	persistState()
	updateElapsed()
}

async function stop() {
	if ((!startTime.value && !segments.value.length) || isSaving.value) return
	if (startTime.value) pushCurrentSegment()
	// Persist the pushed state BEFORE saving: if the save fails and the page
	// is refreshed, the timer must resume exactly here (retryable), not revert
	// to the pre-stop state (which would double-count on the next stop).
	persistState()
	clearInterval(ticker)
	ticker = null
	isSaving.value = true

	try {
		let name = null
		for (const segment of segments.value) {
			name = await call("hrms.api.save_timer_log", {
				employee: employee.data.name,
				from_time: dayjs(segment.from).format("YYYY-MM-DD HH:mm:ss"),
				to_time: dayjs(segment.to).format("YYYY-MM-DD HH:mm:ss"),
				hours: parseFloat((segment.seconds / 3600).toFixed(4)),
				activity_type: segment.activity_type || null,
				project: segment.project || null,
				description: segment.description || null,
			})
		}

		clearPersistedState()
		isRunning.value = false
		isPaused.value = false
		pausedSince.value = null
		segments.value = []
		startTime.value = null
		elapsed.value = 0
		form.value = { project: "", activity_type: "", description: "" }
		clearTimeout(longRunningTimeout)
		restoreTabIndicator()

		toast({
			title: __("Time log saved!"),
			icon: "check",
			iconClasses: "text-green-500",
		})

		// Navigate to the timesheet that was created/updated
		router.push({ name: "TimesheetDetailView", params: { id: name } })
	} catch (e) {
		// Resume the ticker so the timer doesn't lose time
		startTick()
		toast({
			title: __("Failed to save time log"),
			icon: "x",
			iconClasses: "text-red-500",
		})
	} finally {
		isSaving.value = false
	}
}

function discard() {
	clearInterval(ticker)
	ticker = null
	clearPersistedState()
	isRunning.value = false
	isPaused.value = false
	pausedSince.value = null
	segments.value = []
	startTime.value = null
	elapsed.value = 0
	restoreTabIndicator()
}

// ─── Lifecycle ───────────────────────────────────────────────────────────────

onMounted(() => {
	try { baseTitle = document.title || "" } catch { baseTitle = "" }
	loadFavorites(); loadProjects(); loadPersistedState(); refreshTabIndicator()
})
onUnmounted(() => { clearInterval(ticker); clearTimeout(pauseTimeout); clearTimeout(longRunningTimeout); restoreTabIndicator() })
</script>
