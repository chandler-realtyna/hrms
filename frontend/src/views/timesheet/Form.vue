<template>
	<WeeklyForm v-if="mode === 'weekly'" :id="props.id" />
	<LegacyForm v-else-if="mode === 'legacy'" :id="props.id" />
	<ion-page v-else>
		<ion-content :fullscreen="true">
			<div class="h-full flex items-center justify-center text-sm text-gray-500">
				{{ __("Loading timesheet…") }}
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, inject, onMounted } from "vue"
import { IonPage, IonContent } from "@ionic/vue"
import { call } from "frappe-ui"

import WeeklyForm from "@/views/timesheet/WeeklyForm.vue"
import LegacyForm from "@/views/timesheet/LegacyForm.vue"

const __ = inject("$translate")
const props = defineProps({ id: { type: String, required: false } })
const mode = ref(props.id ? null : "weekly")

onMounted(async () => {
	if (!props.id) return
	const result = await call("hrms.api.weekly_timesheet.get_timesheet_mode", {
		name: props.id,
	})
	mode.value = result.is_weekly ? "weekly" : "legacy"
})
</script>
