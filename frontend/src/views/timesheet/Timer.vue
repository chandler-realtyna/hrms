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
					</div>
					<div v-else-if="elapsed > 0" class="mt-3 text-sm text-gray-400">
						{{ __("Stopped") }}
					</div>
					<div v-else class="mt-3 text-sm text-gray-400">
						{{ __("Press Start to begin tracking") }}
					</div>
				</div>

				<div v-if="favoriteProjects.length" class="mx-4 mt-3">
					<div class="mb-2 text-sm font-semibold text-gray-700">{{ __("Favorite projects") }}</div>
					<div class="flex flex-col gap-2">
						<div v-for="project in favoriteProjects" :key="project.name" class="flex items-center gap-2 rounded-xl border bg-white px-3 py-2 shadow-sm">
							<button class="flex min-w-0 flex-1 items-center gap-2 text-left" @click="selectProject(project.name)">
								<FeatherIcon name="heart" class="h-4 w-4 fill-amber-400 text-amber-500" />
								<span class="truncate text-sm font-medium text-gray-800">{{ project.label || project.name }}</span>
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
					<button type="button" class="-mt-2 self-start text-xs text-gray-500" @click="showProjectList = !showProjectList">
						{{ showProjectList ? __("Hide project list") : __("Browse projects") }}
					</button>
					<div v-if="showProjectList && availableProjects.length" class="max-h-40 overflow-y-auto rounded-lg border bg-gray-50 p-1">
						<div v-for="project in availableProjects" :key="project.name" class="flex items-center gap-2 px-2 py-1.5 text-sm">
							<button class="min-w-0 flex-1 truncate text-left text-gray-700" @click="selectProject(project.name)">{{ project.label || project.name }}</button>
							<button type="button" @click="toggleFavorite(project.name)" :aria-label="__('Toggle favorite')">
								<FeatherIcon name="heart" class="h-4 w-4" :class="isFavorite(project.name) ? 'fill-amber-400 text-amber-500' : 'text-gray-400'" />
							</button>
						</div>
					</div>
					<button v-if="form.project" type="button" class="-mt-2 self-start text-xs text-gray-500" @click="toggleFavorite(form.project)">
						<FeatherIcon name="heart" class="mr-1 inline h-3.5 w-3.5" :class="isFavorite(form.project) ? 'fill-amber-400 text-amber-500' : ''" />
						{{ isFavorite(form.project) ? __("Remove favorite") : __("Add to favorites") }}
					</button>
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
const showProjectList = ref(false)
const longRunningNotified = ref(false)

let ticker = null
let pauseTimeout = null
let longRunningTimeout = null

// ─── Computed ────────────────────────────────────────────────────────────────

const formattedTime = computed(() => {
	// Depend on the ticker so the active project's display updates every second.
	return formatSeconds(projectSeconds(form.value.project))
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
	else favoriteProjects.value = [{ name: project, label: project }, ...favoriteProjects.value]
	localStorage.setItem(FAVORITES_KEY, JSON.stringify(favoriteProjects.value))
}
function selectProject(project) { form.value.project = project; persistState() }
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
}

async function stop() {
	if ((!startTime.value && !segments.value.length) || isSaving.value) return
	if (startTime.value) pushCurrentSegment()
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
}

// ─── Lifecycle ───────────────────────────────────────────────────────────────

onMounted(() => { loadFavorites(); loadProjects(); loadPersistedState() })
onUnmounted(() => { clearInterval(ticker); clearTimeout(pauseTimeout); clearTimeout(longRunningTimeout) })
</script>
