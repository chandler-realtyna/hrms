<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="min-h-full bg-gray-50">
				<header class="bg-white border-b px-4 py-5 sticky top-0 z-20">
					<div class="max-w-5xl mx-auto flex items-center justify-between gap-3">
						<div>
							<h1 class="text-xl font-semibold text-gray-900">{{ __("Invoices") }}</h1>
							<p class="text-xs text-gray-500 mt-1">
								{{ __("Review worked hours, confirm, and follow payment status.") }}
							</p>
						</div>
						<Button variant="solid" @click="router.push({ name: 'EmployeeInvoiceNewView' })">{{
							__("New invoice")
						}}</Button>
					</div>
				</header>

				<main class="max-w-5xl mx-auto p-4 md:p-6 space-y-6">
					<section>
						<h2 class="text-sm font-semibold text-gray-700 mb-3">{{ __("My invoices") }}</h2>
						<div
							v-if="loading"
							class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500"
						>
							{{ __("Loading…") }}
						</div>
						<div
							v-else-if="mine.length"
							class="bg-white border rounded-xl divide-y overflow-hidden"
						>
							<router-link
								v-for="item in mine"
								:key="item.name"
								:to="{ name: 'EmployeeInvoiceDetailView', params: { id: item.name } }"
								class="flex items-center justify-between gap-4 p-4 hover:bg-gray-50"
							>
								<div>
									<div class="font-medium text-gray-900">{{ item.name }}</div>
									<div class="text-xs text-gray-500 mt-1">
										{{ formatPeriod(item) }} · {{ Number(item.worked_hours || 0).toFixed(2) }}
										{{ __("hours") }}
									</div>
								</div>
								<div class="text-right">
									<div class="font-semibold text-gray-900">
										{{ money(item.grand_total, item.currency) }}
									</div>
									<span class="text-xs px-2 py-1 rounded-full" :class="statusClass(item.status)">{{
										__(item.status)
									}}</span>
								</div>
							</router-link>
						</div>
						<div v-else class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500">
							{{ __("No invoices yet") }}
						</div>
					</section>

					<section v-if="isHR">
						<h2 class="text-sm font-semibold text-gray-700 mb-3">{{ __("HR review queue") }}</h2>
						<div v-if="queue.length" class="bg-white border rounded-xl divide-y overflow-hidden">
							<router-link
								v-for="item in queue"
								:key="item.name"
								:to="{ name: 'EmployeeInvoiceDetailView', params: { id: item.name } }"
								class="grid grid-cols-[1fr_auto] gap-4 p-4 hover:bg-gray-50"
							>
								<div>
									<div class="font-medium text-gray-900">{{ item.employee_name }}</div>
									<div class="text-xs text-gray-500 mt-1">
										{{ item.name }} · {{ item.company }} · {{ formatPeriod(item) }}
									</div>
								</div>
								<div class="text-right">
									<div class="font-semibold">{{ money(item.grand_total, item.currency) }}</div>
									<span class="text-xs px-2 py-1 rounded-full" :class="statusClass(item.status)">{{
										__(item.status)
									}}</span>
								</div>
							</router-link>
						</div>
						<div v-else class="bg-white border rounded-xl p-8 text-center text-sm text-gray-500">
							{{ __("Nothing waiting for HR") }}
						</div>
					</section>
				</main>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { inject, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"
import { Button, call } from "frappe-ui"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const user = inject("$user")
const router = useRouter()
const loading = ref(true)
const mine = ref([])
const queue = ref([])
const isHR = (user.data?.roles || []).some((role) =>
	["HR Manager", "HR User", "System Manager", "Administrator"].includes(role)
)

function formatPeriod(item) {
	return `${dayjs(item.period_start).format("D MMM YYYY")} – ${dayjs(item.period_end).format(
		"D MMM YYYY"
	)}`
}
function money(value, currency) {
	return `${Number(value || 0).toFixed(2)} ${currency || ""}`
}
function statusClass(status) {
	if (status === "Paid") return "bg-green-100 text-green-700"
	if (["Changes Requested", "Pending Employee Confirmation"].includes(status))
		return "bg-red-100 text-red-700"
	if (status?.startsWith("Pending") || status === "Approved for Payment")
		return "bg-amber-100 text-amber-700"
	return "bg-gray-100 text-gray-700"
}

onMounted(async () => {
	try {
		mine.value = await call("hrms.api.employee_invoice.get_my_invoices")
		if (isHR) queue.value = await call("hrms.api.employee_invoice.get_hr_invoice_queue")
	} finally {
		loading.value = false
	}
})
</script>
