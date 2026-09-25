<template>
	<ion-tab-bar
		slot="bottom"
		class="bg-white shadow-md py-2 pb-2 standalone:pb-safe-bottom md:!hidden"
	>
		<ion-tab-button
			v-for="item in tabItems"
			:key="item.title"
			:tab="item.title"
			:routerLink="item.route"
			routerDirection="root"
			:class="[
				'bg-white text-xs space-y-1.5 !hover:border-gray-300 !hover:text-gray-700 transition active:scale-95',
				isActive(item)
					? 'border-gray-900 text-gray-800 font-semibold'
					: 'text-gray-600 font-normal',
			]"
		>
			<component :is="item.icon" class="h-5 w-5" />
			<div>{{ item.title }}</div>
		</ion-tab-button>
	</ion-tab-bar>
</template>

<script setup>
import { useRoute } from "vue-router"

import { IonTabBar, IonTabButton, IonLabel } from "@ionic/vue"

import HomeIcon from "@/components/icons/HomeIcon.vue"
import TimerIcon from "@/components/icons/TimerIcon.vue"
import TimesheetIcon from "@/components/icons/TimesheetIcon.vue"
import AvailabilityIcon from "@/components/icons/AvailabilityIcon.vue"
import { inject } from "vue"

const __ = inject("$translate")

const route = useRoute()

function isActive(item) {
	if (route.path === item.route) return true
	return item.route !== "/home" && route.path.startsWith(item.route + "/")
}

const tabItems = [
	{
		icon: TimerIcon,
		title: __("Timer"),
		route: "/timesheets/timer",
	},
	{
		icon: HomeIcon,
		title: __("Home"),
		route: "/home",
	},
	{
		icon: TimesheetIcon,
		title: __("Timesheets"),
		route: "/timesheets",
	},
	{
		icon: AvailabilityIcon,
		title: __("Team"),
		route: "/availability",
	},
]
</script>
