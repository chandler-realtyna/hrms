<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/docs" /></ion-buttons>
				<ion-title>{{ __("Add Document") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div class="p-4 flex flex-col gap-4">
				<!-- Title -->
				<div>
					<label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
						{{ __("Title") }} *
					</label>
					<input
						v-model="form.title"
						type="text"
						:placeholder="__('e.g. Employee Handbook')"
						class="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
					/>
				</div>

				<!-- URL -->
				<div>
					<label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
						{{ __("Link (URL)") }} *
					</label>
					<input
						v-model="form.url"
						type="url"
						placeholder="https://..."
						class="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
					/>
				</div>

				<!-- Category -->
				<div>
					<label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
						{{ __("Category") }} *
					</label>
					<!-- Existing categories as quick-select chips -->
					<div v-if="existingCategories.length" class="flex flex-wrap gap-2 mb-2">
						<button
							v-for="cat in existingCategories"
							:key="cat"
							@click="form.category = cat"
							:class="[
								'text-xs px-2.5 py-1 rounded-full border transition-colors',
								form.category === cat
									? 'bg-blue-500 text-white border-blue-500'
									: 'bg-white text-gray-600 border-gray-200 hover:border-blue-300',
							]"
						>
							{{ cat }}
						</button>
					</div>
					<input
						v-model="form.category"
						type="text"
						:placeholder="__('e.g. HR Policies, Benefits, Onboarding')"
						class="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
					/>
				</div>

				<!-- Description -->
				<div>
					<label class="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
						{{ __("Description") }}
						<span class="text-gray-400 normal-case tracking-normal font-normal ml-1">
							({{ __("optional") }})
						</span>
					</label>
					<textarea
						v-model="form.description"
						rows="3"
						:placeholder="__('Short description shown below the title')"
						class="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
					/>
				</div>

				<Button
					variant="solid"
					class="w-full mt-2"
					:disabled="!form.title.trim() || !form.url.trim() || !form.category.trim()"
					:loading="saveResource.loading"
					@click="save"
				>
					{{ __("Save Document") }}
				</Button>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, computed, inject } from "vue"
import { useRouter } from "vue-router"
import { createResource, Button, toast } from "frappe-ui"
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent,
} from "@ionic/vue"

const __ = inject("$translate")
const router = useRouter()

const form = ref({ title: "", url: "", category: "", description: "" })

const categoriesResource = createResource({ url: "hrms.api.get_hr_document_categories", auto: true })
const existingCategories = computed(() => categoriesResource.data || [])

const saveResource = createResource({ url: "hrms.api.save_hr_document", auto: false })

function save() {
	saveResource.submit(
		{
			title: form.value.title.trim(),
			url: form.value.url.trim(),
			category: form.value.category.trim(),
			description: form.value.description.trim() || null,
		},
		{
			onSuccess() {
				toast({
					title: __("Saved"),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
				router.push({ name: "Docs" })
			},
			onError(e) {
				toast({
					title: __("Error"),
					text: e.messages?.[0] || __("Failed to save"),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}
</script>
