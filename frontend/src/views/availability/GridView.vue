<template>
	<div class="overflow-x-auto">
		<div :style="{ minWidth: `${Math.max(360, (dates.length + 1) * 90)}px` }">
			<!-- Header row -->
			<div class="grid sticky top-0 z-10 bg-white border-b border-gray-100"
				:style="{ gridTemplateColumns: `140px repeat(${dates.length}, 1fr)` }">
				<div class="px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide border-r border-gray-100">
					{{ __("Employee") }}
				</div>
				<div
					v-for="date in dates"
					:key="date"
					:class="['px-1 py-2 text-center border-r border-gray-50 last:border-r-0', isToday(date) ? 'bg-blue-50' : '']"
				>
					<p class="text-xs font-bold" :class="isToday(date) ? 'text-blue-600' : 'text-gray-700'">
						{{ formatDayLabel(date) }}
					</p>
					<p class="text-xs" :class="isToday(date) ? 'text-blue-500' : 'text-gray-400'">
						{{ formatDateNum(date) }}
					</p>
				</div>
			</div>

			<!-- Empty state -->
			<div v-if="employees.length === 0" class="py-12 text-center text-gray-400 text-sm">
				{{ __("No schedules found for this period.") }}
			</div>

			<!-- Employee rows -->
			<div
				v-for="emp in employees"
				:key="emp.employee"
				class="grid border-b border-gray-50 last:border-b-0 hover:bg-gray-50/50 transition-colors"
				:style="{ gridTemplateColumns: `140px repeat(${dates.length}, 1fr)` }"
			>
				<!-- Name cell -->
				<div class="px-3 py-3 border-r border-gray-100 flex items-center gap-2 min-w-0">
					<div class="w-7 h-7 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
						{{ initials(emp.employee_name) }}
					</div>
					<span class="text-xs font-medium text-gray-800 truncate">{{ emp.employee_name }}</span>
				</div>

				<!-- Day cells -->
				<div
					v-for="date in dates"
					:key="date"
					:class="[
						'px-1 py-2 flex flex-col items-center justify-center gap-0.5 border-r border-gray-50 last:border-r-0 min-h-[2.5rem]',
						isToday(date) ? 'bg-blue-50/40' : '',
					]"
				>
					<!-- Override: leave or holiday -->
					<template v-if="emp.days[date]?.override">
						<span :class="['inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded-md',
							emp.days[date].override === 'leave' ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700']">
							<FeatherIcon :name="emp.days[date].override === 'leave' ? 'umbrella' : 'sun'" class="w-3 h-3 shrink-0" />
							{{ emp.days[date].override === 'leave' ? __('Leave') : __('Holiday') }}
						</span>
					</template>

					<!-- No slots = Off -->
					<template v-else-if="!emp.days[date]?.slots?.length">
						<span class="text-xs text-gray-300">—</span>
					</template>

					<!-- Multiple slots -->
					<template v-else>
						<span
							v-for="(slot, si) in emp.days[date].slots"
							:key="si"
							:class="['text-xs font-semibold px-1.5 py-0.5 rounded-md whitespace-nowrap w-full text-center', slotClass(slot.type)]"
						>
							{{ slotCellLabel(slot) }}
						</span>
					</template>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon } from "frappe-ui"
const __ = inject("$translate")

const props = defineProps({
	dates: { type: Array, required: true },
	employees: { type: Array, required: true },
})

function slotClass(type) {
	switch (type) {
		case "working": return "bg-blue-100 text-blue-700"
		case "on_call": return "bg-orange-100 text-orange-700"
		case "off":     return "bg-gray-100 text-gray-400"
		default:        return "bg-gray-100 text-gray-400"
	}
}

function slotCellLabel(slot) {
	if (slot.type === "off") return "Off"
	if (slot.start && slot.end) return `${shortTime(slot.start)}–${shortTime(slot.end)}`
	if (slot.type === "on_call") return "On-Call"
	return "Work"
}

function shortTime(t) {
	if (!t) return ""
	const [h, m] = t.split(":").map(Number)
	const ampm = h >= 12 ? "pm" : "am"
	const h12 = h % 12 || 12
	return m === 0 ? `${h12}${ampm}` : `${h12}:${String(m).padStart(2, "0")}${ampm}`
}

function isToday(date) {
	const d = new Date()
	const pad = n => String(n).padStart(2, "0")
	return date === `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function formatDayLabel(date) {
	return new Date(date + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" })
}
function formatDateNum(date) {
	return new Date(date + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })
}
function initials(name) {
	if (!name) return "?"
	return name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase()
}
</script>
