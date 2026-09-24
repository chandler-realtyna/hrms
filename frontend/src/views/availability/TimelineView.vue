<template>
	<div>
		<!-- Sticky header: hour axis + timezone/now row stay visible while scrolling -->
		<div class="sticky top-0 z-30 -mx-1 border-b border-gray-100 bg-[var(--ion-background-color,white)] px-1 pb-1 pt-1">
			<!-- Hour axis labels -->
			<div class="flex mb-1 pl-40">
				<div v-for="h in visibleHours" :key="h" class="flex-1 text-center text-xs text-gray-400 font-medium">
					{{ formatHour(h) }}
				</div>
			</div>
			<!-- Timezone label row -->
			<div class="relative pl-40 mb-2">
				<span class="text-[10px] text-gray-400 italic">{{ viewerTzLabel }}</span>
				<div
					v-if="showNowMarker"
					class="absolute top-0 flex -translate-x-1/2 items-center gap-1"
					:style="nowMarkerStyle"
				>
					<span class="h-2 w-2 rounded-full bg-red-500 shadow-sm" />
					<span class="text-[10px] font-semibold text-red-500">{{ __("Now") }}</span>
				</div>
			</div>
		</div>

		<div v-if="activeEmployees.length === 0" class="py-12 text-center text-gray-400 text-sm">
			{{ __("No availability data for this day.") }}
		</div>

		<div v-for="group in employeeGroups" :key="group.key" :class="group.muted ? 'mt-5 border-t border-gray-100 pt-4 opacity-50' : ''">
			<div v-if="group.label && group.employees.length" class="mb-3 pl-40 text-xs font-semibold text-gray-400">
				{{ group.label }}
			</div>

			<div v-if="group.employees.length" class="relative">
				<div
					v-if="showNowMarker && !group.muted"
					class="pointer-events-none absolute top-0 bottom-0 z-20 w-px bg-red-500/80 shadow-[0_0_0_1px_rgba(239,68,68,0.15)]"
					:style="nowMarkerStyle"
				/>

				<div v-for="emp in group.employees" :key="emp.employee" class="flex items-start mb-3">
					<!-- Name label -->
					<div class="w-40 shrink-0 flex items-center gap-2 pr-3 pt-0.5">
						<button
							type="button"
							class="relative flex-shrink-0 rounded-full focus:outline-none"
							:class="isSelected(emp.employee) ? 'ring-2 ring-blue-500 ring-offset-1' : ''"
							@click="$emit('toggleSelect', emp.employee)"
							:aria-label="__('Select person')"
						>
							<img
								v-if="emp.image"
								:src="emp.image"
								:alt="emp.employee_name"
								class="h-7 w-7 rounded-full object-cover"
							/>
							<div v-else class="w-7 h-7 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center">
								{{ initials(emp.employee_name) }}
							</div>
							<span
								v-if="isSelected(emp.employee)"
								class="absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 ring-2 ring-white"
							>
								<FeatherIcon name="check" class="h-2.5 w-2.5 text-white" />
							</span>
						</button>
						<span class="text-xs text-gray-700 font-medium truncate">{{ emp.employee_name }}</span>
					</div>

					<!-- Timeline bar area -->
					<div class="flex-1 relative h-8 bg-gray-50 rounded-lg overflow-hidden border border-gray-100">
						<!-- Override: leave or holiday (full-width) -->
						<template v-if="emp.dayData?.override">
							<div :class="[
								'absolute inset-0 flex items-center justify-center gap-1.5 text-xs font-semibold text-white rounded-lg',
								emp.dayData.override === 'leave' ? 'bg-purple-400' : 'bg-green-400'
							]">
								<FeatherIcon :name="emp.dayData.override === 'leave' ? 'umbrella' : 'sun'" class="w-3.5 h-3.5 shrink-0" />
								{{ emp.dayData.override === 'leave' ? __('On Leave') : __('Holiday') }}
							</div>
						</template>

						<!-- Slots (zero = off) -->
						<template v-else-if="emp.dayData?.slots?.length">
							<div
								v-for="(slot, si) in emp.dayData.slots"
								:key="si"
								:style="barStyle(slot)"
								:class="['absolute top-0 h-full flex items-center justify-center overflow-hidden', barBg(slot.type)]"
							>
								<span class="text-xs font-semibold text-white px-1 truncate drop-shadow-sm select-none">
									{{ barLabel(slot) }}
								</span>
							</div>
						</template>

						<!-- Off all day -->
						<div v-else class="absolute inset-0 flex items-center justify-center">
							<span class="text-xs text-gray-300 font-medium">{{ __("Off") }}</span>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Compare-timezone axis -->
		<div v-if="showCompareAxis" class="mt-3">
			<div class="flex pl-40">
				<div v-for="h in visibleHours" :key="h" class="flex-1 text-center text-xs text-gray-400 font-medium">
					{{ compareHourLabel(h) }}
				</div>
			</div>
			<div class="pl-40 mt-0.5">
				<span class="text-[10px] text-gray-400 italic">{{ compareTzLabel }}</span>
			</div>
		</div>

		<!-- Legend -->
		<div class="flex flex-wrap gap-3 mt-4 pt-3 border-t border-gray-100">
			<div v-for="item in legend" :key="item.type" class="flex items-center gap-1.5">
				<span :class="['w-3 h-3 rounded-sm', item.color]" />
				<span class="text-xs text-gray-500">{{ item.label }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref } from "vue"
import { FeatherIcon } from "frappe-ui"
const __ = inject("$translate")

const props = defineProps({
	date:          { type: String, required: true },
	employees:     { type: Array,  required: true },
	viewerTz:      { type: String, default: "America/New_York" },
	viewerTzLabel: { type: String, default: "your timezone" },
	compareTz:     { type: String, default: "" },
	compareTzLabel: { type: String, default: "" },
	selectedIds:   { type: Array,  default: () => [] },
})

const emit = defineEmits(["toggleSelect"])

function isSelected(employeeId) {
	return (props.selectedIds || []).includes(employeeId)
}

const START_HOUR = 7
const END_HOUR = 22
const TOTAL_HOURS = END_HOUR - START_HOUR
const LABEL_WIDTH_REM = 10

const visibleHours = Array.from({ length: TOTAL_HOURS + 1 }, (_, i) => START_HOUR + i)
const now = ref(new Date())
const nowInterval = setInterval(() => {
	now.value = new Date()
}, 60 * 1000)

onBeforeUnmount(() => {
	clearInterval(nowInterval)
})

const activeEmployees = computed(() =>
	props.employees.map((emp) => ({
		...emp,
		dayData: emp.days?.[props.date] || null,
	}))
)

const currentHour = computed(() => viewerNow.value.hour)

// Wall-clock "now" in the VIEWER's timezone (not the browser's): the axis,
// the day boundary and the Now marker must all agree with the selected zone.
const viewerNow = computed(() => {
	try {
		const parts = new Intl.DateTimeFormat("en-US", {
			timeZone: props.viewerTz,
			year: "numeric",
			month: "2-digit",
			day: "2-digit",
			hour: "2-digit",
			minute: "2-digit",
			hour12: false,
		})
			.formatToParts(now.value)
			.reduce((acc, p) => ({ ...acc, [p.type]: p.value }), {})
		return {
			date: `${parts.year}-${parts.month}-${parts.day}`,
			hour: (Number(parts.hour) % 24) + Number(parts.minute) / 60,
		}
	} catch {
		const d = now.value
		const pad = (n) => String(n).padStart(2, "0")
		return {
			date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
			hour: d.getHours() + d.getMinutes() / 60,
		}
	}
})

const employeeGroups = computed(() => {
	if (!showNowMarker.value) {
		return [{ key: "all", label: "", muted: false, employees: activeEmployees.value }]
	}
	const activeNow = []
	const inactiveNow = []
	for (const emp of activeEmployees.value) {
		if (isEmployeeActiveNow(emp)) activeNow.push(emp)
		else inactiveNow.push(emp)
	}
	return [
		{ key: "active-now", label: "", muted: false, employees: activeNow },
		{ key: "inactive-now", label: __("Not active now"), muted: true, employees: inactiveNow },
	]
})

const showNowMarker = computed(() => {
	if (props.date !== viewerNow.value.date) return false
	return currentHour.value >= START_HOUR && currentHour.value <= END_HOUR
})

const nowMarkerStyle = computed(() => {
	const percent = ((currentHour.value - START_HOUR) / TOTAL_HOURS) * 100
	return {
		left: `calc(${LABEL_WIDTH_REM}rem + ((100% - ${LABEL_WIDTH_REM}rem) * ${percent / 100}))`,
	}
})

function isEmployeeActiveNow(emp) {
	if (emp.dayData?.override) return false
	return (emp.dayData?.slots || []).some((slot) => {
		if (!["working", "on_call"].includes(slot.type)) return false
		if (!slot.start || !slot.end) return false
		return timeToDecH(slot.start) <= currentHour.value && currentHour.value < timeToDecH(slot.end)
	})
}

function barStyle(slot) {
	if (!slot.start || !slot.end) return { left: "0%", width: "0%" }
	const startH = timeToDecH(slot.start)
	const endH   = timeToDecH(slot.end)
	const cs = Math.max(startH, START_HOUR)
	const ce = Math.min(endH, END_HOUR)
	if (ce <= cs) return { display: "none" }
	return {
		left:  `${((cs - START_HOUR) / TOTAL_HOURS) * 100}%`,
		width: `${((ce - cs) / TOTAL_HOURS) * 100}%`,
	}
}

function barBg(type) {
	switch (type) {
		case "working": return "bg-blue-500"
		case "on_call": return "bg-orange-400"
		case "off":     return "bg-gray-300"
		default:        return "bg-gray-300"
	}
}

function barLabel(slot) {
	if (slot.type === "off") return "Off"
	if (slot.start && slot.end) return `${shortTime(slot.start)} – ${shortTime(slot.end)}`
	if (slot.type === "on_call") return "On-Call"
	return "Work"
}

function timeToDecH(t) {
	if (!t) return 0
	const [h, m] = t.split(":").map(Number)
	return h + m / 60
}

function shortTime(t) {
	if (!t) return ""
	const [h, m] = t.split(":").map(Number)
	const ampm = h >= 12 ? "PM" : "AM"
	const h12 = h % 12 || 12
	return m === 0 ? `${h12}${ampm}` : `${h12}:${String(m).padStart(2, "0")}${ampm}`
}

function formatHour(h) {
	const ampm = h >= 12 ? "PM" : "AM"
	const h12 = h % 12 || 12
	return `${h12}${ampm}`
}

function localDateStr(d = new Date()) {
	const pad = n => String(n).padStart(2, "0")
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// ── Compare-timezone axis ────────────────────────────────────────────────────
// Second axis under the rows: for each viewer hour position, show the wall
// time in the compare zone (e.g. viewer 12PM Paris → 6AM EDT).
const showCompareAxis = computed(
	() => Boolean(props.compareTz) && props.compareTz !== props.viewerTz
)

function tzOffsetMinutes(tz, utcMs) {
	try {
		const label =
			new Intl.DateTimeFormat("en-GB", { timeZone: tz, timeZoneName: "shortOffset" })
				.formatToParts(new Date(utcMs))
				.find((p) => p.type === "timeZoneName")?.value ?? "GMT+0"
		const m = label.match(/GMT([+-])(\d+)(?::(\d+))?/)
		if (!m) return 0
		return (m[1] === "+" ? 1 : -1) * (parseInt(m[2], 10) * 60 + parseInt(m[3] ?? "0", 10))
	} catch {
		return 0
	}
}

function compareHourLabel(h) {
	if (!showCompareAxis.value) return ""
	try {
		const [Y, M, D] = props.date.split("-").map(Number)
		const guess = Date.UTC(Y, M - 1, D, h, 0)
		const instant = new Date(guess - tzOffsetMinutes(props.viewerTz, guess) * 60000)
		const parts = new Intl.DateTimeFormat("en-US", {
			timeZone: props.compareTz,
			hour: "numeric",
			minute: "2-digit",
			hour12: true,
		})
			.formatToParts(instant)
			.reduce((acc, p) => ({ ...acc, [p.type]: p.value }), {})
		const h12 = parts.hour
		const suffix = (parts.dayPeriod || "").toUpperCase()
		return parts.minute === "00" ? `${h12}${suffix}` : `${h12}:${parts.minute}${suffix}`
	} catch {
		return ""
	}
}

function initials(name) {
	if (!name) return "?"
	return name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase()
}
const legend = [
	{ type: "working", color: "bg-blue-500",   label: "Working" },
	{ type: "on_call", color: "bg-orange-400",  label: "On-Call" },
	{ type: "leave",   color: "bg-purple-400",  label: "On Leave" },
	{ type: "holiday", color: "bg-green-400",   label: "Holiday" },
]
</script>
