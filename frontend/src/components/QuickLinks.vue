<template>
	<!-- ── Sidebar variant (desktop Quick Links panel) ── -->
	<div v-if="sidebar" class="flex flex-col gap-0.5">
		<p class="px-3 pb-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider mt-4 first:mt-0">
			{{ title || __("Quick Links") }}
		</p>
		<router-link
			v-for="link in items"
			:key="link.title"
			:to="{ name: link.route }"
			class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-gray-600 hover:bg-gray-50 hover:text-gray-900"
		>
			<component :is="link.icon" class="h-4 w-4 shrink-0 text-gray-500" />
			{{ link.title }}
		</router-link>
	</div>

	<!-- ── Default card-list variant (mobile) ── -->
	<div v-else class="flex flex-col gap-5 my-4 w-full">
		<div class="text-lg font-medium text-gray-900">{{ title || __("Quick Links") }}</div>
		<div class="flex flex-col bg-white rounded">
			<router-link
				class="flex flex-row flex-start p-4 items-center justify-between"
				:class="link !== items[items.length - 1] && 'border-b'"
				v-for="link in items"
				:key="link.title"
				:to="{ name: link.route }"
			>
				<div class="flex flex-row items-center gap-3 grow">
					<component :is="link.icon" class="h-5 w-5 text-gray-500" />
					<div class="text-base font-normal text-gray-800">{{ link.title }}</div>
				</div>
				<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
			</router-link>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon } from "frappe-ui"

const __ = inject("$translate")

const props = defineProps({
	title: { type: String, required: false, default: "" },
	items: { type: Array, required: true },
	sidebar: { type: Boolean, default: false },
})

const { items } = props
</script>
