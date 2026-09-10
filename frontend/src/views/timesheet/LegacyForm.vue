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
const isSubmitted = computed(() => timesheet.value.docstatus === 1)
const today = new Date().toISOString().substring(0, 10)

const props = defineProps({
	id: { type: String, required: true },
})

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
	}
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
	const total = logs.reduce((sum, log) => sum + parseFloat(log.hours || 0), 0)
	timesheet.value.total_hours = parseFloat(total.toFixed(2))
}

function validateForm() {}
</script>
