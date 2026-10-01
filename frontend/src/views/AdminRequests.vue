<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/desk" />
				</ion-buttons>
				<ion-title>{{ title }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<main class="mx-auto w-full max-w-4xl p-4 md:p-6">
				<div class="mb-5">
					<h1 class="text-lg font-semibold text-gray-900">{{ title }}</h1>
					<p class="mt-1 text-sm text-gray-500">{{ __("Requests assigned to you for review") }}</p>
				</div>

				<div v-if="requests.loading" class="rounded border bg-white p-8 text-center text-sm text-gray-500">
					{{ __("Loading requests…") }}
				</div>
				<div v-else-if="requests.error" class="rounded border border-red-200 bg-white p-6 text-sm text-red-700">
					{{ __("You do not have permission to review these requests.") }}
				</div>
				<div v-else-if="!items.length" class="rounded border bg-white p-8 text-center text-sm text-gray-500">
					{{ __("No requests are waiting for your review.") }}
				</div>
				<RequestList
					v-else
					:items="items"
					:teamRequests="true"
					:emptyStateMessage="__('No requests are waiting for your review.')"
				/>
			</main>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRoute } from "vue-router"
import { IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, onIonViewWillEnter } from "@ionic/vue"

import RequestList from "@/components/RequestList.vue"
import { requests } from "@/data/adminRequests"

const __ = inject("$translate")
const route = useRoute()
const requestType = computed(() => route.meta.requestType)
const title = computed(() =>
	__(requestType.value === "Leave Application" ? "Leave Requests" : "Expense Requests")
)
const items = computed(() => (requests.data || []).filter((row) => row.doctype === requestType.value))

onIonViewWillEnter(() => requests.reload())
</script>
