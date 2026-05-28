<template>
	<div
		v-if="modelValue"
		class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
		@click.self="$emit('update:modelValue', false)"
	>
		<div class="bg-white w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl shadow-xl p-6">
			<div class="flex items-center justify-between mb-5">
				<h3 class="text-lg font-bold text-gray-900">{{ __("Send Meeting Invitation") }}</h3>
				<button @click="$emit('update:modelValue', false)" class="text-gray-400 hover:text-gray-600">
					<FeatherIcon name="x" class="w-5 h-5" />
				</button>
			</div>

			<!-- Slot summary -->
			<div class="bg-blue-50 rounded-xl p-3 mb-5 text-sm">
				<p class="font-medium text-blue-900">{{ slot?.date }} · {{ slot?.start }} – {{ slot?.end }} UTC</p>
				<p class="text-blue-600 mt-1">{{ participants.length }} {{ __("participants") }}</p>
			</div>

			<div class="space-y-3">
				<div>
					<label class="block text-xs font-medium text-gray-600 mb-1">{{ __("Meeting Title") }}</label>
					<input
						v-model="title"
						type="text"
						:placeholder="__('e.g. Weekly Sync')"
						class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-400"
					/>
				</div>
				<div>
					<label class="block text-xs font-medium text-gray-600 mb-1">{{ __("Description / Agenda") }}</label>
					<textarea
						v-model="description"
						rows="3"
						:placeholder="__('What will you discuss?')"
						class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-400 resize-none"
					/>
				</div>
			</div>

			<div v-if="error" class="mt-3 bg-red-50 text-red-600 text-sm rounded-xl p-3">
				{{ error }}
			</div>

			<div class="flex gap-3 mt-5">
				<button
					class="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50"
					@click="$emit('update:modelValue', false)"
				>
					{{ __("Cancel") }}
				</button>
				<button
					:disabled="!title.trim() || sending"
					:class="[
						'flex-1 py-2.5 rounded-xl text-sm font-semibold transition-colors',
						title.trim() && !sending
							? 'bg-blue-600 text-white hover:bg-blue-700'
							: 'bg-gray-100 text-gray-400 cursor-not-allowed'
					]"
					@click="send"
				>
					<span v-if="sending" class="flex items-center justify-center gap-2">
						<div class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
						{{ __("Sending...") }}
					</span>
					<span v-else>{{ __("Send Invitation") }}</span>
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from "vue"
import { FeatherIcon, toast, call } from "frappe-ui"
import { inject } from "vue"

const __ = inject("$translate")

const props = defineProps({
	modelValue: Boolean,
	slot: Object,
	participants: Array,
})
const emit = defineEmits(["update:modelValue", "sent"])

const title = ref("")
const description = ref("")
const sending = ref(false)
const error = ref("")

watch(() => props.modelValue, (v) => {
	if (v) {
		title.value = ""
		description.value = ""
		error.value = ""
	}
})

async function send() {
	if (!title.value.trim()) return
	sending.value = true
	error.value = ""
	try {
		await call("hrms.api.calendar.send_meeting_invitation", {
			employees: JSON.stringify(props.participants),
			start: `${props.slot.date} ${props.slot.start}:00`,
			end: `${props.slot.date} ${props.slot.end}:00`,
			title: title.value.trim(),
			description: description.value.trim(),
		})
		toast({
			title: __("Invitation Sent"),
			text: __("Meeting invitations have been sent to all participants."),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
		emit("sent")
		emit("update:modelValue", false)
	} catch (e) {
		error.value = e?.message || __("Failed to send invitation")
	} finally {
		sending.value = false
	}
}
</script>
