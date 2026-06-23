<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				doctype="Timesheet"
				v-model="timesheet"
				:isSubmittable="true"
				:fields="TIMESHEET_FORM_FIELDS"
				:id="props.id"
				:showAttachmentView="true"
				@validateForm="validateForm"
			>
				<template #time_logs>
					<TimeLogsTable
						v-model:timesheet="timesheet"
						:isReadOnly="isSubmitted"
						:date="timesheet.start_date"
						@addLog="addLog"
						@updateLog="updateLog"
						@deleteLog="deleteLog"
					/>
				</template>
			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { ref, computed, inject, watch } from "vue"

import FormView from "@/components/FormView.vue"
import TimeLogsTable from "@/components/TimeLogsTable.vue"

const employee = inject("$employee")

// isSubmitted drives read-only state ourselves — we do NOT use FormView's
// isFormReadOnly because FormView may enter an error state (e.g. a 403 on
// System Settings for the currency formatter) and incorrectly lock the form.
const isSubmitted = computed(() => timesheet.value.docstatus === 1)

const today = new Date().toISOString().substring(0, 10)

const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// Show a single Date for the whole timesheet (all logs share it), the
// time_logs (slot) and note. Everything else is auto-filled: employee,
// company, end_date (kept in sync with the date), total_hours (calculated).
const TIMESHEET_FORM_FIELDS = [
	{ fieldname: "start_date", fieldtype: "Date", label: "Date", maxDate: today },
	{ fieldname: "time_logs", fieldtype: "Table", label: "Time Logs" },
	{ fieldname: "note", fieldtype: "Text Editor", label: "Note" },
]

const timesheet = ref({
	employee: employee.data.name,
	employee_name: employee.data.employee_name,
	company: employee.data.company,
	start_date: today,
	end_date: today,
})

// The timesheet has a single date. Keep end_date in sync with it and, when the
// user changes the date, move every existing log onto the new date (preserving
// each log's time-of-day / duration portion).
watch(
	() => timesheet.value.start_date,
	(newDate, oldDate) => {
		if (!newDate) return
		timesheet.value.end_date = newDate
		if (!oldDate || oldDate === newDate) return
		;(timesheet.value.time_logs || []).forEach((log) => {
			if (log.from_time) log.from_time = newDate + log.from_time.substring(10)
			if (log.to_time) log.to_time = newDate + log.to_time.substring(10)
		})
	},
)

function addLog(log) {
	if (!timesheet.value.time_logs) timesheet.value.time_logs = []
	timesheet.value.time_logs.push(log)
	recalculateTotals()
}

function updateLog(log, idx) {
	timesheet.value.time_logs[idx] = log
	recalculateTotals()
}

function deleteLog(idx) {
	timesheet.value.time_logs.splice(idx, 1)
	recalculateTotals()
}

function recalculateTotals() {
	const logs = timesheet.value.time_logs || []
	let total = 0
	logs.forEach((log) => { total += parseFloat(log.hours || 0) })
	timesheet.value.total_hours = parseFloat(total.toFixed(2))
	// start_date / end_date track the single timesheet Date (see the watcher above)
}

function validateForm() {}
</script>
