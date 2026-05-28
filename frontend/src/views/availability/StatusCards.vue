<template>
	<div class="space-y-4">
		<div v-if="totalEmployees === 0" class="py-12 text-center text-gray-400 text-sm">
			{{ __("No availability data for this day.") }}
		</div>

		<div
			v-for="group in statusGroups"
			v-show="group.entries.length > 0"
			:key="group.type"
			class="bg-white rounded-2xl shadow-sm border overflow-hidden"
			:class="group.borderColor"
		>
			<!-- Group header -->
			<div :class="['px-4 py-3 flex items-center justify-between border-b', group.headerBg]">
				<div class="flex items-center gap-2">
					<FeatherIcon :name="group.icon" :class="['w-4 h-4', group.textColor]" />
					<span :class="['text-sm font-bold', group.textColor]">{{ group.label }}</span>
				</div>
				<span :class="['text-xs font-semibold px-2.5 py-1 rounded-full', group.badgeBg, group.textColor]">
					{{ group.entries.length }}
				</span>
			</div>

			<!-- Employee chips -->
			<div class="p-3 flex flex-col gap-2">
				<div
					v-for="entry in group.entries"
					:key="entry.employee + '-' + entry.slot?.type"
					class="flex items-center gap-3 bg-gray-50 rounded-xl px-3 py-2.5"
				>
					<div :class="['w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center flex-shrink-0', group.avatarBg]">
						{{ initials(entry.employee_name) }}
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-sm font-semibold text-gray-800 truncate">{{ entry.employee_name }}</p>
						<!-- Slot hours -->
						<p v-if="entry.slot?.start && entry.slot?.end" class="text-xs text-gray-400 mt-0.5">
							{{ shortTime(entry.slot.start) }} – {{ shortTime(entry.slot.end) }} {{ viewerTzLabel }}
						</p>
						<!-- Override label -->
						<p v-else-if="entry.overrideLabel" class="text-xs text-gray-400 mt-0.5">
							{{ entry.overrideLabel }}
						</p>
					</div>
				</div>
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

// Enrich each employee with their day data
const enriched = computed(() =>
	props.employees.map((emp) => ({
		...emp,
		dayData: emp.days?.[props.date] || null,
	}))
)

const totalEmployees = computed(() => enriched.value.length)

// An employee may appear in MULTIPLE groups if they have both Working and On-Call slots.
// Each group entry = {employee, employee_name, slot, overrideLabel}

const GROUP_DEFS = [
	{
		type: "working",
		label: "Working",
		icon: "briefcase",
		borderColor: "border-blue-100",
		headerBg: "bg-blue-50",
		textColor: "text-blue-700",
		badgeBg: "bg-blue-100",
		avatarBg: "bg-blue-100 text-blue-700",
	},
	{
		type: "on_call",
		label: "On-Call",
		icon: "phone",
		borderColor: "border-orange-100",
		headerBg: "bg-orange-50",
		textColor: "text-orange-700",
		badgeBg: "bg-orange-100",
		avatarBg: "bg-orange-100 text-orange-700",
	},
	{
		type: "leave",
		label: "On Leave",
		icon: "umbrella",
		borderColor: "border-purple-100",
		headerBg: "bg-purple-50",
		textColor: "text-purple-700",
		badgeBg: "bg-purple-100",
		avatarBg: "bg-purple-100 text-purple-700",
	},
	{
		type: "holiday",
		label: "Holiday",
		icon: "sun",
		borderColor: "border-green-100",
		headerBg: "bg-green-50",
		textColor: "text-green-700",
		badgeBg: "bg-green-100",
		avatarBg: "bg-green-100 text-green-700",
	},
	{
		type: "off",
		label: "Off",
		icon: "moon",
		borderColor: "border-gray-100",
		headerBg: "bg-gray-50",
		textColor: "text-gray-500",
		badgeBg: "bg-gray-100",
		avatarBg: "bg-gray-100 text-gray-500",
	},
]

const statusGroups = computed(() =>
	GROUP_DEFS.map((def) => {
		const entries = []
		for (const emp of enriched.value) {
			const d = emp.dayData
			if (!d) {
				if (def.type === "off") entries.push({ employee: emp.employee, employee_name: emp.employee_name, slot: null, overrideLabel: null })
				continue
			}
			if (d.override === "leave" && def.type === "leave") {
				entries.push({ employee: emp.employee, employee_name: emp.employee_name, slot: null, overrideLabel: d.override_label })
			} else if (d.override === "holiday" && def.type === "holiday") {
				entries.push({ employee: emp.employee, employee_name: emp.employee_name, slot: null, overrideLabel: "Holiday" })
			} else if (!d.override) {
				// Collect slots matching this group type
				const matching = (d.slots || []).filter((s) => s.type === def.type)
				if (matching.length > 0) {
					for (const slot of matching) {
						entries.push({ employee: emp.employee, employee_name: emp.employee_name, slot, overrideLabel: null })
					}
				} else if (def.type === "off" && !(d.slots || []).some((s) => s.type !== "off")) {
					// Truly off all day (no Working / On-Call slots)
					entries.push({ employee: emp.employee, employee_name: emp.employee_name, slot: null, overrideLabel: null })
				}
			}
		}
		return { ...def, entries }
	})
)

function shortTime(t) {
	if (!t) return ""
	const [h, m] = t.split(":").map(Number)
	const ampm = h >= 12 ? "PM" : "AM"
	const h12 = h % 12 || 12
	return m === 0 ? `${h12} ${ampm}` : `${h12}:${String(m).padStart(2, "0")} ${ampm}`
}

function initials(name) {
	if (!name) return "?"
	return name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase()
}
</script>
