<template>
	<div>
		<!-- Hour axis labels -->
		<div class="flex mb-1 pl-28">
			<div v-for="h in visibleHours" :key="h" class="flex-1 text-center text-xs text-gray-400 font-medium">
				{{ formatHour(h) }}
			</div>
		</div>
		<!-- Timezone label row -->
		<div class="pl-28 mb-2">
			<span class="text-[10px] text-gray-400 italic">{{ viewerTzLabel }}</span>
		</div>

		<div v-if="activeEmployees.length === 0" class="py-12 text-center text-gray-400 text-sm">
			{{ __("No availability data for this day.") }}
		</div>

		<div v-for="emp in activeEmployees" :key="emp.employee" class="flex items-start mb-3">
			<!-- Name label -->
			<div class="w-28 shrink-0 flex items-center gap-1.5 pr-2 pt-1">
				<div class="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
					{{ initials(emp.employee_name) }}
				</div>
				<span class="text-xs text-gray-700 font-medium truncate">{{ firstName(emp.employee_name) }}</span>
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
import { computed, inject } from "vue"
import { FeatherIcon } from "frappe-ui"
const __ = inject("$translate")

const props = defineProps({
	date:          { type: String, required: true },
	employees:     { type: Array,  required: true },
	viewerTzLabel: { type: String, default: "your timezone" },
})

const START_HOUR = 7
const END_HOUR = 22
const TOTAL_HOURS = END_HOUR - START_HOUR

const visibleHours = Array.from({ length: TOTAL_HOURS + 1 }, (_, i) => START_HOUR + i)

const activeEmployees = computed(() =>
	props.employees.map((emp) => ({
		...emp,
		dayData: emp.days?.[props.date] || null,
	}))
)

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

function initials(name) {
	if (!name) return "?"
	return name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase()
}
function firstName(name) {
	return name?.split(" ")[0] || ""
}

const legend = [
	{ type: "working", color: "bg-blue-500",   label: "Working" },
	{ type: "on_call", color: "bg-orange-400",  label: "On-Call" },
	{ type: "leave",   color: "bg-purple-400",  label: "On Leave" },
	{ type: "holiday", color: "bg-green-400",   label: "Holiday" },
]
</script>
