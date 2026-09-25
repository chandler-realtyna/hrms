<template>
	<ion-tab-bar
		slot="bottom"
		class="bg-white shadow-md py-2 pb-2 standalone:pb-safe-bottom md:!hidden"
	>
		<button
			v-for="item in tabItems"
			:key="item.route"
			type="button"
			@click="go(item.route)"
			:class="[
				'flex-1 bg-white text-xs space-y-1.5 transition active:scale-95 flex flex-col items-center justify-center py-1',
				isActive(item)
					? 'text-gray-900 font-semibold'
					: 'text-gray-500 font-normal',
			]"
			:aria-label="item.title"
		>
			<component v-if="typeof item.icon !== 'string'" :is="item.icon" class="h-5 w-5" />
			<FeatherIcon v-else :name="item.icon" class="h-5 w-5" />
			<div>{{ item.title }}</div>
		</button>
	</ion-tab-bar>
</template>

<script setup>
import { useRoute, useRouter } from "vue-router"

import { IonTabBar } from "@ionic/vue"

import { FeatherIcon } from "frappe-ui"
import TimerIcon from "@/components/icons/TimerIcon.vue"
import TimesheetIcon from "@/components/icons/TimesheetIcon.vue"
import AvailabilityIcon from "@/components/icons/AvailabilityIcon.vue"
import { inject } from "vue"

const __ = inject("$translate")

const route = useRoute()
const router = useRouter()

function matchLength(item) {
	if (route.path === item.route) return item.route.length
	if (item.route !== "/home" && route.path.startsWith(item.route + "/")) return item.route.length
	return -1
}

// Longest-prefix match: on /timesheets/timer only Timer lights up,
// on /timesheets/123 only Timesheets. Home never partially matches.
function isActive(item) {
	let best = -1
	for (const t of tabItems) best = Math.max(best, matchLength(t))
	return matchLength(item) === best && best >= 0
}

// Plain buttons + router.push: deterministic navigation that does not depend
// on Ionic tab-router wiring.
function go(path) {
	if (route.path !== path) router.push(path)
}

const tabItems = [
	{
		icon: TimerIcon,
		title: __("Timer"),
		route: "/timesheets/timer",
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
	{
		icon: "menu",
		title: __("Menu"),
		route: "/home",
	},
]
</script>
