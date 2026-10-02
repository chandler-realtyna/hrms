<template>
	<WeeklyForm v-if="mode === 'weekly'" :id="props.id" />
	<LegacyForm v-else-if="mode === 'legacy'" :id="props.id" />
	<ion-page v-else>
		<ion-content :fullscreen="true">
			<div v-if="loadError" role="alert" class="h-full flex flex-col gap-4 items-center justify-center p-6 text-sm text-gray-700">
				<p>{{ loadError }}</p>
				<Button variant="solid" @click="loadMode">{{ __("Retry") }}</Button>
			</div>
			<div v-else class="h-full flex items-center justify-center text-sm text-gray-500">
				{{ __("Loading timesheet…") }}
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, inject, watch } from "vue"
import { IonPage, IonContent, onIonViewWillEnter } from "@ionic/vue"
import { Button, call } from "frappe-ui"

import WeeklyForm from "@/views/timesheet/WeeklyForm.vue"
import LegacyForm from "@/views/timesheet/LegacyForm.vue"

const __ = inject("$translate")
const props = defineProps({ id: { type: String, required: false } })
const mode = ref(props.id ? null : "weekly")
const loadError = ref("")
let requestVersion = 0

async function loadMode() {
	const version = ++requestVersion
	loadError.value = ""
	if (!props.id) { mode.value = "weekly"; return }
	mode.value = null
	let timeout
	try {
		const result = await Promise.race([
			call("hrms.api.weekly_timesheet.get_timesheet_mode", { name: props.id }),
			new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error(__("Could not load the timesheet. Please retry."))), 15000) }),
		])
		if (version === requestVersion) mode.value = result.is_weekly ? "weekly" : "legacy"
	} catch (error) {
		if (version === requestVersion) loadError.value = error?.messages?.[0] || error?.message || __("Could not load the timesheet.")
	} finally { clearTimeout(timeout) }
}
watch(() => props.id, loadMode, { immediate: true })
onIonViewWillEnter(loadMode)
</script>
