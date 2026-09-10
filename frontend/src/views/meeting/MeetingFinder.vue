<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/home" /></ion-buttons>
				<ion-title>{{ __("Meeting Finder") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Not connected state -->
			<div v-if="!calendarStatus.loading && !calendarStatus.data?.is_connected" class="flex flex-col items-center justify-center h-full gap-5 px-6 text-center">
				<div class="w-20 h-20 rounded-2xl bg-orange-50 flex items-center justify-center">
					<FeatherIcon name="calendar" class="w-10 h-10 text-orange-500" />
				</div>
				<div>
					<h2 class="text-xl font-bold text-gray-900">{{ __("Connect Google Calendar First") }}</h2>
					<p class="mt-2 text-sm text-gray-500">
						{{ __("You need to connect your Google Calendar before you can use the Meeting Finder.") }}
					</p>
				</div>
				<Button variant="solid" @click="goToCalendarConnect">
					{{ __("Connect Google Calendar") }}
				</Button>
			</div>

			<!-- Main finder UI -->
			<div v-else class="p-4 space-y-4 max-w-2xl mx-auto pb-24">
				<!-- Participants -->
				<div class="bg-white rounded-2xl shadow-sm p-5">
					<div class="flex items-center justify-between mb-3">
						<h3 class="font-semibold text-gray-900">{{ __("Participants") }}</h3>
						<span :class="[
							'text-xs font-medium px-2 py-0.5 rounded-full',
							selectedEmployees.length >= 2 ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'
						]">
							{{ selectedEmployees.length }} / 2+ {{ __("required") }}
						</span>
					</div>
					<p v-if="selectedEmployees.length < 2" class="text-xs text-amber-600 bg-amber-50 rounded-xl px-3 py-2 mb-3">
						{{ __("Add yourself and at least one other person. The finder looks for times when everyone is free.") }}
					</p>
					<div class="flex flex-wrap gap-2 mb-3">
						<div
							v-for="emp in selectedEmployees"
							:key="emp.name"
							class="flex items-center gap-2 bg-blue-50 text-blue-800 text-xs font-medium rounded-full px-3 py-1.5"
						>
							{{ emp.employee_name }}
							<button @click="removeEmployee(emp.name)" class="text-blue-400 hover:text-blue-600">
								<FeatherIcon name="x" class="w-3 h-3" />
							</button>
						</div>
					</div>
					<!-- Employee search -->
					<div class="relative">
						<input
							v-model="employeeSearch"
							type="text"
							:placeholder="__('Search employees...')"
							class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-400"
						/>
						<div v-if="filteredEmployees.length && employeeSearch" class="absolute z-10 top-full mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
							<button
								v-for="emp in filteredEmployees"
								:key="emp.name"
								class="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 flex items-center gap-3"
								@click="addEmployee(emp)"
							>
								<span class="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-600 shrink-0">
									{{ emp.employee_name?.charAt(0) }}
								</span>
								<div>
									<p class="font-medium text-gray-800">{{ emp.employee_name }}</p>
									<p class="text-xs text-gray-400">{{ emp.designation }}</p>
								</div>
							</button>
						</div>
					</div>
				</div>

				<!-- Duration + Date Range -->
				<div class="bg-white rounded-2xl shadow-sm p-5 space-y-4">
					<div>
						<h3 class="font-semibold text-gray-900 mb-3">{{ __("Duration") }}</h3>
						<div class="flex flex-wrap gap-2">
							<button
								v-for="d in durationOptions"
								:key="d"
								:class="[
									'px-4 py-2 rounded-xl text-sm font-medium border transition-colors',
									selectedDuration === d
										? 'bg-blue-600 text-white border-blue-600'
										: 'bg-white text-gray-700 border-gray-200 hover:border-blue-300'
								]"
								@click="selectedDuration = d"
							>
								{{ d }} {{ __("min") }}
							</button>
						</div>
					</div>

					<div class="grid grid-cols-2 gap-3">
						<div>
							<label class="block text-xs font-medium text-gray-600 mb-1">{{ __("From") }}</label>
							<input
								v-model="fromDate"
								type="date"
								:min="today"
								class="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
							/>
						</div>
						<div>
							<label class="block text-xs font-medium text-gray-600 mb-1">{{ __("To") }}</label>
							<input
								v-model="toDate"
								type="date"
								:min="fromDate || today"
								class="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
							/>
						</div>
					</div>
				</div>

				<div>
					<Button
						variant="solid"
						class="w-full"
						:loading="searching"
						:disabled="!canSearch"
						@click="findSlots"
					>
						<template #prefix>
							<FeatherIcon name="search" class="w-4 h-4" />
						</template>
						{{ __("Find Available Slots") }}
					</Button>
					<p v-if="!canSearch" class="text-xs text-center text-gray-400 mt-2">
						<span v-if="selectedEmployees.length < 2">{{ __("Add at least 2 participants") }}</span>
						<span v-else-if="!fromDate || !toDate">{{ __("Set a date range") }}</span>
					</p>
				</div>

				<!-- Results -->
				<div v-if="slots.length > 0" class="space-y-3">
					<div class="flex items-center justify-between px-1">
						<h3 class="font-semibold text-gray-700 text-sm">
							{{ slots.length }} {{ __("available slots found") }}
						</h3>
						<span class="text-xs text-gray-400">{{ userTimezoneLabel }}</span>
					</div>

					<!-- Group by local date -->
					<template v-for="(daySlots, date) in slotsByDate" :key="date">
						<div class="bg-white rounded-2xl shadow-sm overflow-hidden">
							<div class="px-5 py-3 bg-gray-50 border-b border-gray-100">
								<p class="text-sm font-semibold text-gray-800">{{ date }}</p>
							</div>
							<div class="divide-y divide-gray-50">
								<div
									v-for="slot in daySlots"
									:key="slot.start_utc"
									class="flex items-center justify-between px-5 py-3"
								>
									<div>
										<p class="text-sm font-medium text-gray-900">
											{{ toLocalTime(slot.start_utc) }} – {{ toLocalTime(slot.end_utc) }}
										</p>
										<p class="text-xs text-gray-400 mt-0.5">{{ selectedDuration }} {{ __("minutes") }} · {{ selectedEmployees.length }} {{ __("participants") }}</p>
									</div>
									<button
										class="bg-blue-600 text-white text-xs font-semibold px-4 py-2 rounded-xl hover:bg-blue-700 transition-colors"
										@click="openInviteModal(slot)"
									>
										{{ __("Schedule") }}
									</button>
								</div>
							</div>
						</div>
					</template>
				</div>

				<div v-else-if="searched && !searching" class="text-center py-10 text-gray-400 text-sm">
					{{ __("No overlapping free slots found. Try a different date range or fewer participants.") }}
				</div>
			</div>
		</ion-content>

		<!-- Send invitation modal -->
		<SendInvitationModal
			v-model="showInviteModal"
			:slot="activeSlot"
			:participants="selectedEmployees.map(e => e.name)"
			@sent="handleInviteSent"
		/>
	</ion-page>
</template>

<script setup>
import { ref, computed, inject, onMounted } from "vue"
import { IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons, IonBackButton } from "@ionic/vue"
import { FeatherIcon, createResource, call } from "frappe-ui"
import { useRouter } from "vue-router"

import SendInvitationModal from "./SendInvitationModal.vue"

const __ = inject("$translate")
const router = useRouter()
const currentEmployee = inject("$employee")

const goToCalendarConnect = () => {
	window.location.href = "/hrms/calendar/connect"
}

const calendarStatus = createResource({
	url: "hrms.api.calendar.get_calendar_connection_status",
	auto: true,
})

const allEmployees = createResource({
	url: "hrms.api.get_all_employees",
	auto: true,
})

const durationOptions = [15, 30, 45, 60, 90]
const selectedDuration = ref(30)
const selectedEmployees = ref([])

// Pre-populate with the current user's employee record
onMounted(() => {
	const emp = currentEmployee?.data
	if (emp?.name && emp?.employee_name) {
		selectedEmployees.value = [{ name: emp.name, employee_name: emp.employee_name, designation: emp.designation || "" }]
	}
})
const employeeSearch = ref("")
const today = new Date().toISOString().split("T")[0]
const fromDate = ref(today)
const toDate = ref(today)
const slots = ref([])
const searching = ref(false)
const searched = ref(false)
const showInviteModal = ref(false)
const activeSlot = ref(null)

// User's system timezone
const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone

const userTimezoneLabel = computed(() => {
	try {
		const now = new Date()
		const long = new Intl.DateTimeFormat("en-US", { timeZone: userTimezone, timeZoneName: "long" })
			.formatToParts(now).find(p => p.type === "timeZoneName")?.value || userTimezone
		const offset = new Intl.DateTimeFormat("en-US", { timeZone: userTimezone, timeZoneName: "shortOffset" })
			.formatToParts(now).find(p => p.type === "timeZoneName")?.value || ""
		return offset ? `${long} (${offset})` : long
	} catch {
		return userTimezone
	}
})

// Convert a UTC ISO datetime string to the user's local HH:MM
function toLocalTime(utcIso) {
	try {
		return new Date(utcIso).toLocaleTimeString("en-US", {
			timeZone: userTimezone,
			hour: "2-digit",
			minute: "2-digit",
			hour12: false,
		})
	} catch {
		return utcIso
	}
}

// Convert a UTC ISO datetime string to the user's local date string
function toLocalDate(utcIso) {
	try {
		return new Date(utcIso).toLocaleDateString("en-US", {
			timeZone: userTimezone,
			weekday: "long",
			month: "long",
			day: "numeric",
		})
	} catch {
		return utcIso
	}
}

const filteredEmployees = computed(() => {
	const q = employeeSearch.value.toLowerCase().trim()
	if (!q) return []
	const selectedIds = new Set(selectedEmployees.value.map(e => e.name))
	return (allEmployees.data || [])
		.filter(e => !selectedIds.has(e.name) && e.status === "Active" &&
			(e.employee_name?.toLowerCase().includes(q) || e.designation?.toLowerCase().includes(q)))
		.slice(0, 8)
})

const slotsByDate = computed(() => {
	const grouped = {}
	for (const slot of slots.value) {
		// Group by local date derived from the UTC start time
		const localDate = toLocalDate(slot.start_utc)
		if (!grouped[localDate]) grouped[localDate] = []
		grouped[localDate].push(slot)
	}
	return grouped
})

const canSearch = computed(() =>
	selectedEmployees.value.length >= 2 &&
	selectedDuration.value &&
	fromDate.value &&
	toDate.value
)

function addEmployee(emp) {
	selectedEmployees.value.push(emp)
	employeeSearch.value = ""
}

function removeEmployee(id) {
	selectedEmployees.value = selectedEmployees.value.filter(e => e.name !== id)
}

async function findSlots() {
	searching.value = true
	searched.value = false
	slots.value = []
	try {
		const result = await call("hrms.api.calendar.find_meeting_slots", {
			employees: JSON.stringify(selectedEmployees.value.map(e => e.name)),
			duration_minutes: selectedDuration.value,
			from_date: fromDate.value,
			to_date: toDate.value,
		})
		slots.value = result || []
	} catch (e) {
		slots.value = []
	} finally {
		searching.value = false
		searched.value = true
	}
}

function openInviteModal(slot) {
	activeSlot.value = slot
	showInviteModal.value = true
}

function handleInviteSent() {
	showInviteModal.value = false
}

</script>
