<template>
	<div class="w-full flex flex-col gap-4">
		<!-- ── Header: title + view toggle + period selector ── -->
		<div class="flex items-center justify-between gap-2 flex-wrap">
			<h2 class="text-base font-semibold text-gray-800">{{ __("Working Hours") }}</h2>

			<div class="flex items-center gap-2">
				<!-- Me / Team toggle -->
				<div class="flex rounded-lg overflow-hidden border border-gray-200">
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
							{{ hoursData.total ?? 0 }}
						</span>
						<span class="text-sm text-gray-500">{{ __("hours") }}</span>
						<span class="text-xs text-gray-400 ml-auto">{{ periodLabel }}</span>
					</div>

					<!-- Bar chart -->
					<div v-if="hasHours" class="flex flex-col gap-1.5">
						<div class="flex items-end gap-0.5" style="height: 80px">
							<div
								v-for="day in hoursData.daily"
								:key="day.date"
								class="flex-1 rounded-t transition-all duration-300 cursor-default"
								:class="
									isToday(day.date)
										? 'bg-blue-600'
										: day.hours > 0
										? 'bg-blue-400 hover:bg-blue-500'
										: 'bg-gray-100'
								"
								:style="{ height: `${barHeight(day.hours)}%` }"
								:title="`${formatDateFull(day.date)}: ${day.hours}h`"
							/>
						</div>
						<!-- X labels -->
						<div class="flex gap-0.5">
							<div
								v-for="(day, idx) in hoursData.daily"
								:key="day.date"
								class="flex-1 text-center"
							>
								<span
									v-if="showXLabel(idx)"
									class="text-[9px] leading-none"
									:class="isToday(day.date) ? 'text-blue-600 font-semibold' : 'text-gray-400'"
								>
									{{ xLabel(day.date) }}
								</span>
							</div>
						</div>
					</div>

					<p v-else class="text-sm text-gray-400 text-center py-6">
						{{ __("No hours logged in this period") }}
					</p>
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
							<span class="text-sm text-gray-700 truncate">{{ proj.project }}</span>
							<span class="text-xs font-semibold text-gray-500 shrink-0 tabular-nums">
								{{ proj.hours }}h
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
									{{ emp.total_hours }}h
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

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")

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

const todayStr = dayjs().format("YYYY-MM-DD")

// Custom range — defaults to the last 7 days until the user picks dates.
const customFrom = ref(dayjs().subtract(6, "day").format("YYYY-MM-DD"))
const customTo   = ref(todayStr)

const toDate   = computed(() => {
	if (period.value === "custom") return customTo.value
	return todayStr
})
const fromDate = computed(() => {
	if (period.value === "custom") return customFrom.value
	const days = PERIODS.find((p) => p.value === period.value)?.days ?? 7
	return dayjs().subtract(days - 1, "day").format("YYYY-MM-DD")
})

const periodLabel = computed(() => {
	if (period.value === "custom") {
		return `${dayjs(fromDate.value).format("D MMM")} – ${dayjs(toDate.value).format("D MMM")}`
	}
	const days = PERIODS.find((p) => p.value === period.value)?.days ?? 7
	return `last ${days} days`
})

// ─── Resources ─────────────────────────────────────────────────────────────────

const hoursResource = createResource({ url: "hrms.api.get_working_hours_summary",    auto: false })
const projectResource = createResource({ url: "hrms.api.get_employee_project_summary", auto: false })
const teamResource  = createResource({ url: "hrms.api.get_team_working_hours_summary", auto: false })

const hoursData   = computed(() => hoursResource.data  || { daily: [], total: 0 })
const projectData = computed(() => projectResource.data || [])
const hasHours    = computed(() => (hoursData.value.daily || []).some((d) => d.hours > 0))

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
	const params = {
		employee:  employee.data.name,
		from_date: fromDate.value,
		to_date:   toDate.value,
	}
	hoursResource.submit(params)
	projectResource.submit(params)
}

function fetchTeam() {
	teamResource.submit({
		from_date: fromDate.value,
		to_date:   toDate.value,
	})
}

function selectView(value) {
	view.value = value
	if (value === "me")   fetchMe()
	if (value === "team") fetchTeam()
}

function selectPeriod(value) {
	period.value = value
	refetch()
}

function refetch() {
	if (view.value === "me")   fetchMe()
	if (view.value === "team") fetchTeam()
}

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

function showXLabel(idx) {
	const n    = hoursData.value.daily?.length ?? 7
	const step = n <= 7 ? 1 : n <= 14 ? 2 : 5
	return idx % step === 0 || idx === n - 1
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
fetchMe()
</script>
