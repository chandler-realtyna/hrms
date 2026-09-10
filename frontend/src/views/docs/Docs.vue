<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/home" /></ion-buttons>
				<ion-title>{{ __("Documents") }}</ion-title>
				<ion-buttons v-if="isHR" slot="end">
					<ion-button @click="$router.push({ name: 'DocsForm' })">
						<FeatherIcon name="plus" class="h-5 w-5" />
					</ion-button>
				</ion-buttons>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<!-- Loading -->
			<div v-if="docsResource.loading" class="flex items-center justify-center h-48">
				<ion-spinner name="crescent" />
			</div>

			<!-- Empty state -->
			<div v-else-if="!groupedDocs.length"
				class="flex flex-col items-center justify-center h-64 text-gray-400 px-6">
				<FeatherIcon name="file-text" class="h-12 w-12 mb-3 text-gray-200" />
				<p class="text-sm font-medium">{{ __("No documents yet") }}</p>
				<p v-if="isHR" class="text-xs mt-1 text-gray-400 text-center">
					{{ __("Tap the + button to add a document link") }}
				</p>
			</div>

			<!-- Grouped list -->
			<div v-else class="mx-4 mt-4 pb-10 flex flex-col gap-6">
				<div v-for="group in groupedDocs" :key="group.category">
					<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 px-1">
						{{ group.category }}
					</h3>
					<div class="bg-white rounded-xl border border-gray-100 overflow-hidden shadow-sm">
						<div
							v-for="(doc, idx) in group.docs"
							:key="doc.name"
							class="flex items-center gap-3 px-4 py-3"
							:class="idx !== group.docs.length - 1 && 'border-b border-gray-50'"
						>
							<!-- Link: opens URL -->
							<a
								:href="doc.url"
								target="_blank"
								rel="noopener noreferrer"
								class="flex items-center gap-3 flex-1 min-w-0 active:opacity-60"
							>
								<div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
									<FeatherIcon name="link" class="h-4 w-4 text-blue-500" />
								</div>
								<div class="flex-1 min-w-0">
									<p class="text-sm font-medium text-gray-800 truncate">{{ doc.title }}</p>
									<p v-if="doc.description" class="text-xs text-gray-400 mt-0.5 truncate">
										{{ doc.description }}
									</p>
								</div>
								<FeatherIcon name="external-link" class="h-4 w-4 text-gray-300 shrink-0" />
							</a>

							<!-- HR-only delete button -->
							<button
								v-if="isHR"
								@click="confirmDelete(doc)"
								class="ml-2 text-gray-300 hover:text-red-400 active:text-red-500 transition-colors shrink-0"
							>
								<FeatherIcon name="trash-2" class="h-4 w-4" />
							</button>
						</div>
					</div>
				</div>
			</div>

			<ion-refresher slot="fixed" @ionRefresh="refresh($event)">
				<ion-refresher-content />
			</ion-refresher>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { createResource, FeatherIcon, toast } from "frappe-ui"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonButton,
	IonContent, IonSpinner, IonRefresher, IonRefresherContent,
	alertController,
} from "@ionic/vue"

const __ = inject("$translate")

const userInfo = createResource({ url: "hrms.api.get_current_user_info", auto: true })
const isHR = computed(() => {
	const roles = userInfo.data?.roles || []
	return roles.some((r) =>
		["HR Manager", "HR User", "System Manager", "Administrator"].includes(r)
	)
})

const docsResource = createResource({ url: "hrms.api.get_hr_documents", auto: true })

const groupedDocs = computed(() => {
	const docs = docsResource.data || []
	const map = {}
	for (const doc of docs) {
		const cat = doc.category || "General"
		if (!map[cat]) map[cat] = []
		map[cat].push(doc)
	}
	return Object.entries(map)
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([category, docs]) => ({ category, docs }))
})

async function confirmDelete(doc) {
	const alert = await alertController.create({
		header: __("Delete Document"),
		message: `${__("Delete")} "${doc.title}"?`,
		buttons: [
			{ text: __("Cancel"), role: "cancel" },
			{ text: __("Delete"), role: "destructive", handler: () => deleteDoc(doc.name) },
		],
	})
	await alert.present()
}

const deleteResource = createResource({ url: "hrms.api.delete_hr_document", auto: false })

function deleteDoc(name) {
	deleteResource.submit(
		{ name },
		{
			onSuccess() {
				docsResource.reload()
				toast({
					title: __("Deleted"),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError(e) {
				toast({
					title: __("Error"),
					text: e.messages?.[0] || __("Failed to delete"),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}

function refresh(event) {
	docsResource.reload()
	const check = setInterval(() => {
		if (!docsResource.loading) {
			clearInterval(check)
			event.target.complete()
		}
	}, 100)
}
</script>
