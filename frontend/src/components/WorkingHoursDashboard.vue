<template>
	<div class="w-full flex flex-col gap-4">
		<!-- ── Header: title + view toggle + period selector ── -->
		<div class="flex items-center justify-between gap-2 flex-wrap">
			<h2 class="text-base font-semibold text-gray-800">{{ __("Working Hours") }}</h2>

			<div class="flex items-center gap-2">
				<!-- Me / Team toggle (leads + HR only: team hours are scoped to
				     projects they lead, everyone else sees their own hours) -->
				<div v-if="canViewTeam" class="flex rounded-lg overflow-hidden border border-gray-200">
					<button
						v-for="v in VIEWS"
						:key="v.value"
						@click="selectView(v.value)"
						class="px-3 py-1.5 text-xs font-medium transition-colors"
						:class="
							view === v.value
								? 'bg-gray-800 text-white'
								: 'bg-white text-gray-500 hover:bg-gray-50'
						"
					>
						{{ v.label }}
					</button>
				</div>

				<!-- Period selector -->
				<div class="flex items-center gap-1">
					<button
						v-if="period !== 'custom'"
						@click="stepPeriod(-1)"
						class="px-2 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
						:aria-label="__('Previous period')"
					>
						‹
					</button>
					<div class="flex rounded-lg overflow-hidden border border-gray-200">
						<button
							v-for="opt in PERIODS"
							:key="opt.value"
							@click="selectPeriod(opt.value)"
							class="px-3 py-1.5 text-xs font-medium transition-colors"
							:class="
								period === opt.value
									? 'bg-gray-800 text-white'
									: 'bg-white text-gray-500 hover:bg-gray-50'
							"
						>
							{{ opt.label }}
						</button>
					</div>
					<button
						v-if="period !== 'custom'"
						@click="stepPeriod(1)"
						:disabled="periodOffset >= 0"
						class="px-2 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 disabled:opacity-40"
						:aria-label="__('Next period')"
					>
						›
					</button>
				</div>
			</div>
		</div>

		<!-- ── Custom date range pickers (only when 'Custom' is selected) ── -->
		<div
			v-if="period === 'custom'"
			class="flex items-end gap-3 flex-wrap bg-white rounded-xl border p-3"
		>
			<label class="flex flex-col gap-1">
				<span class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">
					{{ __("From") }}
				</span>
				<input
					type="date"
					:max="customTo"
					v-model="customFrom"
					class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-[11px] font-medium text-gray-500 uppercase tracking-wide">
					{{ __("To") }}
				</span>
				<input
					type="date"
					:min="customFrom"
					:max="todayStr"
					v-model="customTo"
					class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
				/>
			</label>
		</div>

		<!-- ══════════════════════════════════════════════════ -->
		<!-- ME view                                           -->
		<!-- ══════════════════════════════════════════════════ -->
		<template v-if="view === 'me'">
			<!-- Hours card -->
			<div class="bg-white rounded-xl border p-4">
				<!-- Loading -->
				<div v-if="hoursResource.loading" class="h-32 flex items-center justify-center">
					<LoadingIndicator class="h-5 w-5 text-gray-400" />
				</div>

				<template v-else>
					<!-- Total -->
					<div class="mb-4 flex items-baseline gap-2">
						<span class="text-4xl font-bold text-gray-900 tabular-nums">
							{{ formatHours(hoursData.total) }}
						</span>
						<span class="text-xs text-gray-400 ml-auto">{{ periodLabel }}</span>
					</div>

					<!-- Every day has a readable duration; long ranges scroll instead of compressing labels. -->
					<div v-if="hasHours" class="working-hours-chart-wrap">
						<div class="working-hours-chart-legend text-gray-400">{{ __("Hours:minutes") }}</div>
						<div class="working-hours-chart-scroll" tabindex="0" :aria-label="__('Daily working hours')">
							<div
								class="working-hours-chart"
								role="list"
								:style="{ gridTemplateColumns: `repeat(${hoursData.daily.length}, minmax(40px, 1fr))` }"
							>
								<div
									v-for="day in hoursData.daily"
									:key="day.date"
									class="working-hours-chart-day"
									role="listitem"
									:aria-label="`${formatDateFull(day.date)}: ${formatHours(day.hours)}`"
									:title="`${formatDateFull(day.date)}: ${formatHours(day.hours)}`"
								>
									<span class="working-hours-chart-value" :class="day.hours > 0 ? 'text-gray-700' : 'text-gray-400'">
										{{ day.hours > 0 ? formatHours(day.hours) : '—' }}
									</span>
									<div class="working-hours-chart-track">
										<div
											class="w-full rounded-t transition-all duration-300 cursor-default"
											:class="isToday(day.date) ? 'bg-blue-600' : day.hours > 0 ? 'bg-blue-400 hover:bg-blue-500' : 'bg-gray-100'"
											:style="{ height: `${barHeight(day.hours)}%` }"
										/>
									</div>
									<span class="working-hours-chart-date" :class="isToday(day.date) ? 'text-blue-600 font-semibold' : 'text-gray-400'">
										{{ xLabel(day.date) }}
									</span>
								</div>
							</div>
						</div>
					</div>

					<p v-else class="text-sm text-gray-400 text-center py-6">
						{{ __("No hours logged in this period") }}
					</p>

					<!-- Detailed stats (timesheet page) -->
					<div v-if="detailed && hasHours" class="grid grid-cols-3 gap-2 mt-4 pt-4 border-t">
						<div class="flex flex-col">
							<span class="text-lg font-bold text-gray-900 tabular-nums">{{ stats.daysLogged }}</span>
							<span class="text-[11px] text-gray-400">{{ __("Days logged") }}</span>
						</div>
						<div class="flex flex-col">
							<span class="text-lg font-bold text-gray-900 tabular-nums">{{ formatHours(stats.avgPerDay) }}</span>
							<span class="text-[11px] text-gray-400">{{ __("Avg / logged day") }}</span>
						</div>
						<div class="flex flex-col">
							<span class="text-lg font-bold text-gray-900 tabular-nums">{{ formatHours(stats.busiest.hours) }}</span>
							<span class="text-[11px] text-gray-400 truncate">{{ stats.busiest.label }}</span>
						</div>
					</div>
				</template>
			</div>

			<!-- Projects card -->
			<div v-if="projectData.length > 0" class="bg-white rounded-xl border p-4">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">{{ __("My Projects") }}</h3>
				<div class="flex flex-col gap-3">
					<div
						v-for="proj in projectData"
						:key="proj.project"
						class="flex flex-col gap-1"
					>
						<div class="flex justify-between items-baseline gap-2">
							<span class="text-sm text-gray-700 truncate" :title="projectLabel(proj.project, ' - ')">{{ projectLabel(proj.project, " - ") }}</span>
							<span class="text-xs font-semibold text-gray-500 shrink-0 tabular-nums">
								{{ formatHours(proj.hours) }}
							</span>
						</div>
						<div class="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
							<div
								class="h-full bg-blue-400 rounded-full transition-all duration-500"
								:style="{ width: `${Math.max((proj.hours / projectData[0].hours) * 100, 4)}%` }"
							/>
						</div>
					</div>
				</div>
			</div>

			<!-- Activity breakdown card (detailed / timesheet page) -->
			<div v-if="detailed && activityData.length > 0" class="bg-white rounded-xl border p-4">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">{{ __("By Activity") }}</h3>
				<div class="flex flex-col gap-3">
					<div
						v-for="act in activityData"
						:key="act.activity_type"
						class="flex flex-col gap-1"
					>
						<div class="flex justify-between items-baseline gap-2">
							<span class="text-sm text-gray-700 truncate">{{ act.activity_type }}</span>
							<span class="text-xs font-semibold text-gray-500 shrink-0 tabular-nums">
								{{ formatHours(act.hours) }}
							</span>
						</div>
						<div class="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
							<div
								class="h-full bg-emerald-400 rounded-full transition-all duration-500"
								:style="{ width: `${Math.max((act.hours / activityData[0].hours) * 100, 4)}%` }"
							/>
						</div>
					</div>
				</div>
			</div>

			<!-- Per-day breakdown (detailed / timesheet page) -->
			<div v-if="detailed && loggedDays.length > 0" class="bg-white rounded-xl border p-4">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">{{ __("By Day") }}</h3>
				<div class="flex flex-col divide-y divide-gray-50">
					<div
						v-for="day in loggedDays"
						:key="day.date"
						class="flex items-center justify-between py-2 first:pt-0 last:pb-0"
					>
						<span
							class="text-sm"
							:class="isToday(day.date) ? 'text-blue-600 font-semibold' : 'text-gray-700'"
						>
							{{ formatDateFull(day.date) }}
							<span v-if="isToday(day.date)" class="text-[10px] text-blue-400 ml-1">
								{{ __("Today") }}
							</span>
						</span>
						<span class="text-sm font-semibold text-gray-800 tabular-nums">{{ formatHours(day.hours) }}</span>
					</div>
				</div>
			</div>
		</template>

		<!-- ══════════════════════════════════════════════════ -->
		<!-- TEAM view                                         -->
		<!-- ══════════════════════════════════════════════════ -->
		<template v-else>
			<div class="bg-white rounded-xl border p-4">
				<!-- Loading -->
				<div v-if="teamResource.loading" class="h-32 flex items-center justify-center">
					<LoadingIndicator class="h-5 w-5 text-gray-400" />
				</div>

				<template v-else-if="teamData.length === 0">
					<p class="text-sm text-gray-400 text-center py-6">
						{{ __("No team hours logged in this period") }}
					</p>
				</template>

				<template v-else>
					<!-- Legend / viewer tz -->
					<div class="flex items-center justify-between mb-4">
						<span class="text-xs text-gray-500">
							{{ __("Offset relative to you") }} ({{ viewerTzLabel }})
						</span>
						<span class="text-xs text-gray-400">{{ periodLabel }}</span>
					</div>

					<!-- Employee rows -->
					<div class="flex flex-col divide-y divide-gray-50">
						<div
							v-for="emp in teamData"
							:key="emp.employee"
							class="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
						>
							<!-- Avatar -->
							<div
								:class="[
									'w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center shrink-0',
									emp.isMe ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700',
								]"
							>
								{{ initials(emp.employee_name) }}
							</div>

							<!-- Name + timezone badge -->
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2 flex-wrap">
									<span class="text-sm font-semibold text-gray-800 truncate">
										{{ emp.isMe ? __("You") : emp.employee_name }}
									</span>
									<!-- Offset chip (only shown when we know the employee's tz) -->
									<span
										v-if="emp.timezone && !emp.isMe"
										:class="[
											'inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0',
											offsetChipClass(emp.offsetHours),
										]"
									>
										{{ emp.offsetLabel }}
									</span>
									<span
										v-else-if="emp.isMe"
										class="inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 shrink-0"
									>
										{{ viewerTzLabel }}
									</span>
								</div>
								<!-- Timezone name (small) -->
								<p v-if="emp.timezone && !emp.isMe" class="text-[10px] text-gray-400 mt-0.5 truncate">
									{{ emp.timezone }}
								</p>
							</div>

							<!-- Hours + mini bar -->
							<div class="flex flex-col items-end gap-1 shrink-0">
								<span class="text-sm font-bold text-gray-900 tabular-nums">
									{{ formatHours(emp.total_hours) }}
								</span>
								<!-- Mini bar relative to team max -->
								<div class="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
									<div
										:class="[
											'h-full rounded-full transition-all duration-500',
											emp.isMe ? 'bg-blue-600' : 'bg-blue-300',
										]"
										:style="{ width: `${teamBarWidth(emp.total_hours)}%` }"
									/>
								</div>
							</div>
						</div>
					</div>
				</template>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, computed, inject, watch } from "vue"
import { createResource, LoadingIndicator } from "frappe-ui"
import { getViewerTimezone, getTimezoneAbbr, getOffsetDiffHours, formatOffsetDiff } from "@/utils/timezone.js"
import { formatHours } from "@/utils/formatters.js"
import { useProjectLabels } from "@/composables/useProjectLabels.js"

const { displayName: projectLabel, load: loadProjectLabels } = useProjectLabels()
loadProjectLabels()

const props = defineProps({
	// When true, render extra breakdowns (stats, activity, per-day list).
	detailed: { type: Boolean, default: false },
})

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

// The employee home shows team controls only for an actual project lead.
// Managerial permissions and the Desk queues remain unchanged.
const userInfo = createResource({ url: "hrms.api.get_current_user_info", auto: true })
const canViewTeam = computed(() => Boolean(userInfo.data?.has_led_projects))

// ── Viewer timezone ────────────────────────────────────────────────────────────
const viewerTz      = getViewerTimezone()
const viewerTzLabel = getTimezoneAbbr(viewerTz)

// ── Config ─────────────────────────────────────────────────────────────────────

const VIEWS = [
	{ label: "Me",   value: "me"   },
	{ label: "Team", value: "team" },
]

const PERIODS = [
	{ label: "Week",   value: "week",   days: 7  },
	{ label: "2W",     value: "2weeks", days: 14 },
	{ label: "Month",  value: "month",  days: 30 },
	{ label: "Custom", value: "custom" },
]

const view   = ref("me")
const period = ref("week")
// Browse past calendar periods: 0 = current, -1 = previous, … (never future).
const periodOffset = ref(0)

const todayStr = dayjs().format("YYYY-MM-DD")

function toISODate(d) {
	const pad = (n) => String(n).padStart(2, "0")
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function shiftDays(dateStr, n) {
	const d = new Date(dateStr + "T12:00:00")
	d.setDate(d.getDate() + n)
	return toISODate(d)
}
function mondayOf(dateStr) {
	const d = new Date(dateStr + "T12:00:00")
	const day = d.getDay() // 0=Sun
	d.setDate(d.getDate() + (day === 0 ? -6 : 1 - day))
	return toISODate(d)
}
function firstOfMonth(dateStr) {
	return dateStr.slice(0, 7) + "-01"
}
function shiftMonths(dateStr, n) {
	const d = new Date(dateStr.slice(0, 7) + "-01T12:00:00")
	d.setMonth(d.getMonth() + n)
	return toISODate(d)
}
function clampToday(dateStr) {
	return dateStr > todayStr ? todayStr : dateStr
}

// Calendar-aligned ranges matching timesheet weeks (Mon–Sun), so Monday
// never shows a confusing mix of two timesheet weeks.
const toDate   = computed(() => {
	if (period.value === "custom") return customTo.value
	if (period.value === "month") {
		const first = shiftMonths(firstOfMonth(todayStr), periodOffset.value)
		return clampToday(shiftDays(shiftMonths(first, 1), -1))
	}
	const span = period.value === "2weeks" ? 14 : 7
	const monday = shiftDays(mondayOf(todayStr), periodOffset.value * span)
	return clampToday(shiftDays(monday, span - 1))
})
const fromDate = computed(() => {
	if (period.value === "custom") return customFrom.value
	if (period.value === "month") return shiftMonths(firstOfMonth(todayStr), periodOffset.value)
	const span = period.value === "2weeks" ? 14 : 7
	return shiftDays(mondayOf(todayStr), periodOffset.value * span)
})

// Custom range — defaults to the last 7 days until the user picks dates.
const customFrom = ref(dayjs().subtract(6, "day").format("YYYY-MM-DD"))
const customTo   = ref(todayStr)

const periodLabel = computed(() => {
	if (period.value === "custom") {
		return `${dayjs(fromDate.value).format("D MMM")} – ${dayjs(toDate.value).format("D MMM")}`
	}
	const range = `${dayjs(fromDate.value).format("D MMM")} – ${dayjs(toDate.value).format("D MMM")}`
	return periodOffset.value === 0 ? `${range} · ${__("this period")}` : range
})

function stepPeriod(dir) {
	if (period.value === "custom") return
	periodOffset.value = Math.min(0, periodOffset.value + dir)
	refetch()
}

// ─── Resources ─────────────────────────────────────────────────────────────────

const hoursResource = createResource({ url: "hrms.api.get_working_hours_summary",    auto: false })
const projectResource = createResource({ url: "hrms.api.get_employee_project_summary", auto: false })
const activityResource = createResource({ url: "hrms.api.get_employee_activity_summary", auto: false })
const teamResource  = createResource({ url: "hrms.api.get_team_working_hours_summary", auto: false })

const hoursData    = computed(() => hoursResource.data  || { daily: [], total: 0 })
const projectData  = computed(() => projectResource.data || [])
const activityData = computed(() => activityResource.data || [])
const hasHours     = computed(() => (hoursData.value.daily || []).some((d) => d.hours > 0))

// Only the days that actually have logged hours (for the detailed per-day list).
const loggedDays = computed(() => (hoursData.value.daily || []).filter((d) => d.hours > 0))

// Aggregate stats derived from the daily data (detailed mode).
const stats = computed(() => {
	const days = loggedDays.value
	if (!days.length) return { daysLogged: 0, avgPerDay: 0, busiest: { hours: 0, label: "" } }
	const total = days.reduce((sum, d) => sum + d.hours, 0)
	const busiest = days.reduce((a, b) => (b.hours > a.hours ? b : a), days[0])
	return {
		daysLogged: days.length,
		avgPerDay: parseFloat((total / days.length).toFixed(1)),
		busiest: { hours: busiest.hours, label: __("Busiest: {0}", [dayjs(busiest.date).format("ddd D MMM")]) },
	}
})

// ── Team data enriched with timezone deltas ────────────────────────────────────
const teamData = computed(() => {
	const raw = teamResource.data || []
	if (!raw.length) return []

	const myId = employee.data?.name

	return raw.map((emp) => {
		const isMe = emp.employee === myId
		const offsetHours = emp.timezone
			? getOffsetDiffHours(viewerTz, emp.timezone)
			: null
		return {
			...emp,
			isMe,
			offsetHours,
			offsetLabel: offsetHours !== null ? formatOffsetDiff(offsetHours) : "",
		}
	})
})

const teamMaxHours = computed(() =>
	Math.max(...(teamData.value || []).map((e) => e.total_hours), 1)
)

function teamBarWidth(hours) {
	return Math.max((hours / teamMaxHours.value) * 100, 3)
}

// ── Actions ────────────────────────────────────────────────────────────────────

function fetchMe() {
	const empName = employee?.data?.name
	// Never throw during setup: if employee data isn't ready yet, the watcher
	// below retries as soon as it arrives. A throw here would abort the whole
	// page mount and leave the previous route's view stuck on screen.
	if (!empName) return
	const params = {
		employee:  empName,
		from_date: fromDate.value,
		to_date:   toDate.value,
	}
	hoursResource.submit(params)
	projectResource.submit(params)
	if (props.detailed) activityResource.submit(params)
}

function fetchTeam() {
	if (!canViewTeam.value) return
	teamResource.submit({
		from_date: fromDate.value,
		to_date:   toDate.value,
	})
}

function selectView(value) {
	if (value === "team" && !canViewTeam.value) value = "me"
	view.value = value
	if (value === "me")   fetchMe()
	if (value === "team") fetchTeam()
}

function selectPeriod(value) {
	period.value = value
	periodOffset.value = 0
	refetch()
}

function refetch() {
	if (view.value === "me")   fetchMe()
	if (view.value === "team") fetchTeam()
}

// If access resolves to Me-only while Team is selected, fall back to Me.
watch(canViewTeam, (allowed) => {
	if (!allowed && view.value === "team") selectView("me")
})

// Re-fetch when the user adjusts the custom range (only relevant in 'custom' mode).
watch([customFrom, customTo], () => {
	if (period.value === "custom") refetch()
})

// ── Me chart helpers ───────────────────────────────────────────────────────────

const maxHours = computed(() =>
	Math.max(...(hoursData.value.daily || []).map((d) => d.hours), 1)
)

function barHeight(hours) {
	if (hours === 0) return 3
	return Math.max((hours / maxHours.value) * 100, 6)
}

function isToday(date) {
	return date === toDate.value
}

function formatDateFull(date) {
	return dayjs(date).format("ddd, D MMM")
}

function xLabel(date) {
	const n = hoursData.value.daily?.length ?? 7
	return n <= 14
		? dayjs(date).format("dd")[0]
		: dayjs(date).format("D")
}

// ── Team helpers ───────────────────────────────────────────────────────────────

function initials(name) {
	if (!name) return "?"
	return name
		.split(" ")
		.slice(0, 2)
		.map((n) => n[0])
		.join("")
		.toUpperCase()
}

function offsetChipClass(hours) {
	if (hours === null) return "bg-gray-100 text-gray-500"
	if (hours === 0)    return "bg-gray-100 text-gray-600"
	if (hours > 0)      return "bg-amber-50 text-amber-700"
	return "bg-sky-50 text-sky-700"
}

// ── Init ────────────────────────────────────────────────────────────────────────
// Fetch immediately when employee data is ready; otherwise wait for it instead
// of throwing (see fetchMe).
if (employee?.data?.name) {
	fetchMe()
} else {
	const stopEmployeeWatch = watch(
		() => employee?.data?.name,
		(name) => {
			if (name) {
				stopEmployeeWatch()
				fetchMe()
			}
		}
	)
}
</script>


<style scoped>
.working-hours-chart-wrap { min-width: 0; }
.working-hours-chart-legend { margin-bottom: 4px; font-size: 10px; }
.working-hours-chart-scroll { overflow-x: auto; max-width: 100%; padding-bottom: 4px; }
.working-hours-chart { display: grid; column-gap: 2px; }
.working-hours-chart-day { display: grid; grid-template-rows: 18px 80px 14px; gap: 4px; min-width: 40px; }
.working-hours-chart-value { font-size: 11px; line-height: 18px; text-align: center; white-space: nowrap; font-variant-numeric: tabular-nums; }
.working-hours-chart-track { display: flex; align-items: flex-end; height: 80px; }
.working-hours-chart-date { font-size: 9px; line-height: 14px; text-align: center; }
</style>
