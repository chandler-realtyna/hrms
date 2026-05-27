<template>
	<div class="flex flex-col gap-3 mt-2">
		<!-- Existing rows -->
		<div
			v-if="timesheet.time_logs?.length"
			class="flex flex-col bg-white rounded border overflow-hidden"
		>
			<div
				v-for="(log, idx) in timesheet.time_logs"
				:key="idx"
				class="flex flex-row items-center justify-between p-3.5"
				:class="idx !== timesheet.time_logs.length - 1 && 'border-b'"
			>
				<div class="flex flex-col gap-1 grow">
					<div class="flex flex-row items-center justify-between">
						<span class="text-sm font-medium text-gray-800">
							{{ log.activity_type || __("No Activity") }}
						</span>
						<span class="text-sm font-semibold text-blue-600">
							{{ formatDuration(log.hours) }}
						</span>
					</div>
					<div v-if="log.description" class="text-xs text-gray-600 mt-0.5">
						{{ log.description }}
					</div>
					<div v-if="log.project" class="text-xs text-gray-400">
						{{ log.project }}
					</div>
				</div>
				<div v-if="!isReadOnly" class="flex flex-row items-center gap-2 ml-3">
					<button class="text-gray-400 hover:text-blue-500" @click="openEdit(idx)">
						<FeatherIcon name="edit-2" class="h-4 w-4" />
					</button>
					<button class="text-gray-400 hover:text-red-500" @click="$emit('deleteLog', idx)">
						<FeatherIcon name="trash-2" class="h-4 w-4" />
					</button>
				</div>
			</div>
		</div>

		<!-- Add row button -->
		<button
			v-if="!isReadOnly"
			class="flex flex-row items-center gap-2 text-sm text-blue-500 font-medium py-2"
			@click="openAdd"
		>
			<FeatherIcon name="plus" class="h-4 w-4" />
			{{ __("Add Time Log") }}
		</button>

		<!-- Add / Edit modal -->
		<ion-modal :is-open="showModal" @did-dismiss="closeModal">
			<ion-header>
				<ion-toolbar>
					<ion-title>{{ editIndex === null ? __("Add Time Log") : __("Edit Time Log") }}</ion-title>
					<ion-buttons slot="end">
						<ion-button @click="closeModal">{{ __("Cancel") }}</ion-button>
					</ion-buttons>
				</ion-toolbar>
			</ion-header>

			<div class="overflow-y-auto flex flex-col gap-4 p-4 bg-white h-full">
				<!-- Description — most prominent field -->
				<FormField
					fieldtype="Small Text"
					fieldname="description"
					:label="__('What did you work on?')"
					:placeholder="__('Describe your work…')"
					v-model="currentLog.description"
				/>

				<!-- Duration in minutes -->
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
						<span class="text-sm text-gray-500">{{ __("min") }}</span>
						<span v-if="currentLog._minutes > 0" class="text-xs text-gray-400 ml-1">
							({{ formatDuration(currentLog._minutes / 60) }})
						</span>
					</div>
				</div>

				<!-- Activity Type -->
				<FormField
					fieldtype="Link"
					fieldname="activity_type"
					:label="__('Activity Type')"
					options="Activity Type"
					v-model="currentLog.activity_type"
				/>

				<!-- Project -->
				<FormField
					fieldtype="Link"
					fieldname="project"
					:label="__('Project')"
					options="Project"
					v-model="currentLog.project"
				/>

				<Button
					variant="solid"
					class="w-full mt-2"
					:disabled="!currentLog._minutes || currentLog._minutes <= 0"
					@click="saveLog"
				>
					{{ editIndex === null ? __("Add") : __("Update") }}
				</Button>
			</div>
		</ion-modal>
	</div>
</template>

<script setup>
import { ref } from "vue"
import { inject } from "vue"
import {
	IonModal, IonHeader, IonToolbar, IonTitle,
	IonButtons, IonButton,
} from "@ionic/vue"
import { FeatherIcon, Button } from "frappe-ui"
import FormField from "@/components/FormField.vue"

const __ = inject("$translate")

const props = defineProps({
	timesheet: { type: Object, required: true },
	isReadOnly: { type: Boolean, default: false },
})

const emit = defineEmits(["update:timesheet", "addLog", "updateLog", "deleteLog"])

const showModal = ref(false)
const currentLog = ref({})
const editIndex = ref(null)

// ── Modal open/close ────────────────────────────────────────────────────────

function openAdd() {
	editIndex.value = null
	currentLog.value = { _minutes: null, activity_type: "", project: "", description: "" }
	showModal.value = true
}

function openEdit(idx) {
	editIndex.value = idx
	const log = props.timesheet.time_logs[idx]
	currentLog.value = {
		...log,
		// Convert stored hours back to minutes for editing
		_minutes: log.hours ? Math.round(log.hours * 60) : null,
	}
	showModal.value = true
}

function closeModal() {
	showModal.value = false
	currentLog.value = {}
	editIndex.value = null
}

// ── Save ────────────────────────────────────────────────────────────────────

function saveLog() {
	const minutes = Number(currentLog.value._minutes)
	if (!minutes || minutes <= 0) return

	const hours = parseFloat((minutes / 60).toFixed(4))

	// Generate from_time / to_time as naive local-time strings for Frappe.
	// Never use .toISOString() here — that converts to UTC and creates an
	// offset equal to the user's timezone (e.g. +4 h for UTC+4 users).
	const now = new Date()
	const pad = n => String(n).padStart(2, "0")
	const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`

	const toTotalSec = minutes * 60
	const toH = pad(Math.floor(toTotalSec / 3600) % 24)
	const toM = pad(Math.floor((toTotalSec % 3600) / 60))
	const toS = pad(toTotalSec % 60)

	const log = {
		activity_type: currentLog.value.activity_type || null,
		project:       currentLog.value.project || null,
		description:   currentLog.value.description || null,
		hours,
		from_time: `${today} 00:00:00`,
		to_time:   `${today} ${toH}:${toM}:${toS}`,
		is_billable: 1,
	}

	if (editIndex.value !== null) {
		emit("updateLog", log, editIndex.value)
	} else {
		emit("addLog", log)
	}
	closeModal()
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Format decimal hours as "Xh Ym" */
function formatDuration(hours) {
	if (!hours || hours <= 0) return ""
	const totalMinutes = Math.round(hours * 60)
	const h = Math.floor(totalMinutes / 60)
	const m = totalMinutes % 60
	if (h === 0) return `${m}m`
	if (m === 0) return `${h}h`
	return `${h}h ${m}m`
}
</script>
