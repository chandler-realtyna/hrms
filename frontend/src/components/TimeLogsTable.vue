<template>
	<div class="flex flex-col gap-3 mt-2">
		<div
			v-if="timesheet.time_logs?.length"
			class="flex flex-col bg-white rounded-xl border overflow-hidden"
		>
			<div
				v-for="(log, idx) in sortedLogs"
				:key="log.name || `${log.from_time}-${idx}`"
				class="flex items-start justify-between p-3.5"
				:class="idx !== sortedLogs.length - 1 && 'border-b'"
			>
				<div class="flex flex-col gap-1 grow min-w-0">
					<div class="flex items-center justify-between gap-3">
						<span class="text-sm font-semibold text-gray-800 truncate">
							{{ log.project }}
						</span>
						<span class="text-sm font-semibold text-blue-600 whitespace-nowrap">
							{{ formatDuration(log.hours) }}
						</span>
					</div>
					<div class="text-xs text-gray-500">
						{{ formatLogTime(log) }}
						<span v-if="log.activity_type && log.activity_type !== 'Unassigned'">
							· {{ log.activity_type }}
						</span>
					</div>
					<div v-if="log.description" class="text-xs text-gray-600 truncate">
						{{ log.description }}
					</div>
					<div v-if="!rowEditable(log) && !isReadOnly" class="text-[11px] text-amber-600">
						{{ __("Approved project — locked") }}
					</div>
				</div>
				<div v-if="rowEditable(log)" class="flex items-center gap-2 ml-3 pt-0.5">
					<button class="text-gray-400 hover:text-blue-500" @click="openEdit(originalIndex(log))">
						<FeatherIcon name="edit-2" class="h-4 w-4" />
					</button>
					<button
						class="text-gray-400 hover:text-red-500"
						@click="$emit('deleteLog', originalIndex(log))"
					>
						<FeatherIcon name="trash-2" class="h-4 w-4" />
					</button>
				</div>
			</div>
		</div>

		<button
			v-if="!isReadOnly"
			class="flex items-center gap-2 text-sm text-blue-600 font-medium py-2"
			@click="openAdd"
		>
			<FeatherIcon name="plus" class="h-4 w-4" />
			{{ __("Add time entry") }}
		</button>

		<ion-modal :is-open="showModal" class="ion-disable-focus-trap" @did-dismiss="closeModal">
			<ion-header>
				<ion-toolbar>
					<ion-title>{{
						editIndex === null ? __("Add time entry") : __("Edit time entry")
					}}</ion-title>
					<ion-buttons slot="end">
						<ion-button @click="closeModal">{{ __("Cancel") }}</ion-button>
					</ion-buttons>
				</ion-toolbar>
			</ion-header>

			<div class="overflow-y-auto flex flex-col gap-4 p-4 bg-white h-full">
				<FormField
					v-if="isWeekly"
					fieldtype="Date"
					fieldname="log_date"
					:label="__('Date')"
					:minDate="weekStart"
					:maxDate="weekEnd"
					v-model="currentLog._date"
				/>
				<div v-if="isWeekly" class="flex flex-col gap-1.5">
					<label class="block text-sm leading-5 text-gray-700">
						{{ __("Start time") }}
					</label>
					<input
						type="time"
						v-model="currentLog._start_time"
						class="w-full border border-gray-200 rounded-lg bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
					/>
				</div>

				<FormField
					fieldtype="Link"
					fieldname="project"
					:label="__('Project')"
					options="Project"
					linkQuery="hrms.api.search_employee_projects"
					v-model="currentLog.project"
					:reqd="true"
				/>

				<FormField
					fieldtype="Link"
					fieldname="activity_type"
					:label="__('Activity Type (optional)')"
					options="Activity Type"
					v-model="currentLog.activity_type"
				/>

				<FormField
					fieldtype="Small Text"
					fieldname="description"
					:label="__('What did you work on?')"
					:placeholder="__('Short description')"
					v-model="currentLog.description"
				/>
				<p class="-mt-2 text-xs text-gray-500">
					{{ __("For Support projects, include the ticket ID or link.") }}
				</p>

				<div>
					<label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
						{{ __("Duration") }}
					</label>
					<div class="flex items-center gap-2">
						<input
							type="number"
							min="1"
							step="1"
							v-model.number="currentLog._minutes"
							class="w-28 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
							:placeholder="__('minutes')"
						/>
						<span class="text-sm text-gray-500">{{ __("minutes") }}</span>
					</div>
				</div>

				<p v-if="formError" class="text-sm text-red-600">{{ formError }}</p>

				<Button variant="solid" class="w-full mt-2" @click="saveLog">
					{{ editIndex === null ? __("Add") : __("Update") }}
				</Button>
			</div>
		</ion-modal>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { IonModal, IonHeader, IonToolbar, IonTitle, IonButtons, IonButton } from "@ionic/vue"
import { FeatherIcon, Button } from "frappe-ui"
import FormField from "@/components/FormField.vue"

const __ = inject("$translate")
const props = defineProps({
	timesheet: { type: Object, required: true },
	isReadOnly: { type: Boolean, default: false },
	date: { type: String, default: "" },
	weekStart: { type: String, default: "" },
	weekEnd: { type: String, default: "" },
	editableProjects: { type: Array, default: () => [] },
})

const emit = defineEmits(["update:timesheet", "addLog", "updateLog", "deleteLog"])
const showModal = ref(false)
const currentLog = ref({})
const editIndex = ref(null)
const formError = ref("")
const isWeekly = computed(() => Boolean(props.weekStart))
const sortedLogs = computed(() =>
	[...(props.timesheet.time_logs || [])].sort((a, b) =>
		String(a.from_time || "").localeCompare(String(b.from_time || ""))
	)
)

const pad = (value) => String(value).padStart(2, "0")
function localDateStr(date) {
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function defaultDate() {
	const today = localDateStr(new Date())
	if (!isWeekly.value) return props.date || today
	if (today < props.weekStart) return props.weekStart
	if (today > props.weekEnd) return props.weekEnd
	return today
}

function rowEditable(log) {
	if (props.isReadOnly) return false
	if (!props.editableProjects.length) return true
	return props.editableProjects.includes(log.project)
}

function originalIndex(log) {
	return props.timesheet.time_logs.indexOf(log)
}

function openAdd() {
	editIndex.value = null
	formError.value = ""
	currentLog.value = {
		_date: defaultDate(),
		_start_time: "09:00",
		_minutes: null,
		project: props.editableProjects.length === 1 ? props.editableProjects[0] : "",
		activity_type: "",
		description: "",
	}
	showModal.value = true
}

function openEdit(idx) {
	editIndex.value = idx
	formError.value = ""
	const log = props.timesheet.time_logs[idx]
	currentLog.value = {
		...log,
		_date: String(log.from_time || "").substring(0, 10),
		_start_time: String(log.from_time || "").substring(11, 16) || "09:00",
		_minutes: log.hours ? Math.round(log.hours * 60) : null,
	}
	showModal.value = true
}

function closeModal() {
	showModal.value = false
	currentLog.value = {}
	editIndex.value = null
	formError.value = ""
}

function addMinutes(date, startTime, minutes) {
	const [year, month, day] = date.split("-").map(Number)
	const [hours, mins] = startTime.split(":").map(Number)
	const value = new Date(year, month - 1, day, hours, mins + minutes, 0, 0)
	return `${localDateStr(value)} ${pad(value.getHours())}:${pad(value.getMinutes())}:00`
}

function saveLog() {
	const minutes = Number(currentLog.value._minutes)
	const date = isWeekly.value ? currentLog.value._date : props.date || defaultDate()
	const startTime = isWeekly.value ? currentLog.value._start_time : "00:00"
	if (!currentLog.value.project) {
		formError.value = __("Project is required")
		return
	}
	if (!date || !startTime || !minutes || minutes <= 0) {
		formError.value = __("Date, start time, and duration are required")
		return
	}

	const log = {
		name: currentLog.value.name || null,
		activity_type: currentLog.value.activity_type || "Unassigned",
		project: currentLog.value.project,
		description: currentLog.value.description || null,
		hours: parseFloat((minutes / 60).toFixed(4)),
		from_time: `${date} ${startTime}:00`,
		to_time: addMinutes(date, startTime, minutes),
		is_billable: currentLog.value.is_billable || 0,
	}

	if (editIndex.value !== null) emit("updateLog", log, editIndex.value)
	else emit("addLog", log)
	closeModal()
}

function formatDuration(hours) {
	const totalMinutes = Math.round((hours || 0) * 60)
	const wholeHours = Math.floor(totalMinutes / 60)
	const minutes = totalMinutes % 60
	if (!wholeHours) return `${minutes}m`
	if (!minutes) return `${wholeHours}h`
	return `${wholeHours}h ${minutes}m`
}

function formatLogTime(log) {
	const from = String(log.from_time || "")
	const to = String(log.to_time || "")
	if (!from) return ""
	return `${from.substring(0, 10)} · ${from.substring(11, 16)}–${to.substring(11, 16)}`
}
</script>
