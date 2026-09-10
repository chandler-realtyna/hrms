<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<div class="min-h-full bg-gray-50">
				<header class="bg-white border-b px-4 py-4 sticky top-0 z-20">
					<div class="max-w-4xl mx-auto flex items-center justify-between gap-3">
						<div class="flex items-center gap-2">
							<Button variant="ghost" @click="router.push({ name: 'EmployeeInvoiceListView' })"
								><FeatherIcon name="chevron-left" class="w-5"
							/></Button>
							<div>
								<h1 class="text-xl font-semibold text-gray-900">
									{{ doc?.name || __("New invoice") }}
								</h1>
								<p v-if="doc" class="text-xs text-gray-500 mt-1">
									{{ doc.employee_name }} · {{ doc.status }}
								</p>
							</div>
						</div>
						<a
							v-if="doc?.name"
							:href="pdfUrl"
							target="_blank"
							class="text-sm font-medium text-blue-700"
							>{{ __("Download PDF") }}</a
						>
					</div>
				</header>

				<main class="max-w-4xl mx-auto p-4 md:p-6 space-y-5">
					<div
						v-if="error"
						class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
					>
						{{ error }}
					</div>
					<div
						v-if="loading"
						class="bg-white border rounded-xl p-10 text-center text-sm text-gray-500"
					>
						{{ __("Loading…") }}
					</div>

					<section v-else-if="!doc" class="bg-white border rounded-xl p-5 max-w-lg">
						<h2 class="font-semibold text-gray-900">{{ __("Create invoice") }}</h2>
						<p class="text-sm text-gray-500 mt-1 mb-4">
							{{ __("The default period starts on the same day one month before the due date.") }}
						</p>
						<label class="text-sm font-medium text-gray-700">{{ __("Due date") }}</label>
						<input
							v-model="newDueDate"
							type="date"
							class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
						/>
						<Button variant="solid" class="mt-4 w-full" :loading="saving" @click="createInvoice">{{
							__("Create and calculate")
						}}</Button>
					</section>

					<template v-else>
						<div v-if="doc.return_reason" class="rounded-xl border border-red-200 bg-red-50 p-4">
							<div class="font-medium text-red-800">{{ __("Changes requested") }}</div>
							<div class="text-sm text-red-700 mt-1">{{ doc.return_reason }}</div>
						</div>

						<section class="grid md:grid-cols-2 gap-4">
							<div class="bg-white border rounded-xl p-5 space-y-3">
								<h2 class="font-semibold text-gray-900">{{ __("Invoice period") }}</h2>
								<Field label="Due date"
									><input
										v-model="form.due_date"
										:disabled="!effectiveEdit"
										type="date"
										class="field"
								/></Field>
								<div class="grid grid-cols-2 gap-3">
									<Field label="Period start"
										><input
											v-model="form.period_start"
											:disabled="!effectiveEdit"
											type="date"
											class="field" /></Field
									><Field label="Period end"
										><input
											v-model="form.period_end"
											:disabled="!effectiveEdit"
											type="date"
											class="field"
									/></Field>
								</div>
								<Field label="Due hours"
									><input
										v-model.number="form.due_hours"
										:disabled="!effectiveEdit"
										type="number"
										min="0"
										step="0.01"
										class="field"
								/></Field>
							</div>
							<div class="bg-white border rounded-xl p-5 space-y-3">
								<h2 class="font-semibold text-gray-900">{{ __("Calculation") }}</h2>
								<Row label="Method" :value="doc.calculation_method" /><Row
									label="Worked hours"
									:value="Number(doc.worked_hours).toFixed(2)"
								/><Row
									label="Paid leave hours"
									:value="Number(doc.paid_leave_hours).toFixed(2)"
								/><Row
									label="Sick leave hours"
									:value="Number(doc.sick_leave_hours).toFixed(2)"
								/><Row
									label="Unpaid leave hours"
									:value="Number(doc.unpaid_leave_hours).toFixed(2)"
								/><Row label="Payable hours" :value="Number(doc.payable_hours).toFixed(2)" /><Row
									:label="
										doc.calculation_method === 'Hourly' ? __('Hourly rate') : __('Monthly amount')
									"
									:value="
										money(
											doc.calculation_method === 'Hourly' ? doc.hourly_rate : doc.monthly_amount
										)
									"
								/><Row label="Base amount" :value="money(doc.base_amount)" /><Row
									label="Unpaid leave deduction"
									:value="money(doc.unpaid_leave_deduction)"
								/>
								<div class="pt-3 border-t flex justify-between text-lg font-semibold">
									<span>{{ __("Total") }}</span
									><span>{{ money(doc.grand_total) }}</span>
								</div>
								<div
									class="text-xs"
									:class="doc.time_approval_ready ? 'text-green-700' : 'text-amber-700'"
								>
									{{
										doc.time_approval_ready
											? __("All used timesheets are finalized.")
											: __("HR approval is blocked until all used timesheets are finalized.")
									}}
								</div>
								<div v-if="canHREdit" class="grid grid-cols-2 gap-3 pt-3 border-t">
									<Field label="Currency"><input v-model="form.currency" class="field" /></Field
									><Field
										:label="doc.calculation_method === 'Hourly' ? 'Hourly rate' : 'Monthly amount'"
										><input
											v-model.number="
												form[
													doc.calculation_method === 'Hourly' ? 'hourly_rate' : 'monthly_amount'
												]
											"
											type="number"
											min="0"
											step="0.01"
											class="field"
									/></Field>
								</div>
							</div>
						</section>

						<section class="bg-white border rounded-xl p-5 space-y-3">
							<h2 class="font-semibold text-gray-900">{{ __("Payee and payment") }}</h2>
							<div class="grid md:grid-cols-2 gap-3">
								<Field label="Legal payee name"
									><input
										v-model="form.payee_name"
										:disabled="!effectiveEdit"
										class="field" /></Field
								><Field label="Preferred payment method"
									><select
										v-model="form.preferred_payment_method"
										:disabled="!effectiveEdit"
										class="field"
									>
										<option v-for="method in paymentMethods" :key="method">{{ method }}</option>
									</select></Field
								>
							</div>
							<Field label="Payee address">
								<textarea
									v-model="form.payee_address"
									:disabled="!effectiveEdit"
									class="field"
									rows="2"
								/>
							</Field>
							<Field label="Payment details">
								<textarea
									v-model="form.payment_details"
									:disabled="!effectiveEdit"
									class="field"
									rows="2"
									placeholder="Wise account, wallet and network, cash instructions, or other details"
								/>
							</Field>
							<div
								v-if="form.preferred_payment_method === 'Bank Transfer'"
								class="grid md:grid-cols-3 gap-3"
							>
								<Field label="Bank"
									><input
										v-model="form.bank_name"
										:disabled="!effectiveEdit"
										class="field" /></Field
								><Field label="Account number"
									><input
										v-model="form.bank_account_no"
										:disabled="!effectiveEdit"
										class="field" /></Field
								><Field label="IBAN"
									><input v-model="form.iban" :disabled="!effectiveEdit" class="field"
								/></Field>
							</div>
							<Field label="Employee notes">
								<textarea
									v-model="form.employee_note"
									:disabled="!effectiveEdit"
									class="field"
									rows="3"
								/>
							</Field>
						</section>

						<section class="bg-white border rounded-xl p-5">
							<h2 class="font-semibold text-gray-900 mb-3">{{ __("Time summary") }}</h2>
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead>
										<tr class="text-left text-gray-500 border-b">
											<th class="py-2">{{ __("Date") }}</th>
											<th>{{ __("Timesheet") }}</th>
											<th class="text-right">{{ __("Hours") }}</th>
											<th class="text-right">{{ __("Status") }}</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="row in doc.time_summary"
											:key="`${row.timesheet}-${row.date}`"
											class="border-b last:border-0"
										>
											<td class="py-2">{{ row.date }}</td>
											<td>{{ row.timesheet }}</td>
											<td class="text-right">{{ Number(row.hours).toFixed(2) }}</td>
											<td
												class="text-right"
												:class="row.status === 'Finalized' ? 'text-green-700' : 'text-amber-700'"
											>
												{{ __(row.status) }}
											</td>
										</tr>
										<tr v-if="!doc.time_summary.length">
											<td colspan="4" class="py-6 text-center text-gray-500">
												{{ __("No recorded hours in this period") }}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
							<div
								v-if="doc.leave_summary"
								class="mt-4 text-sm bg-gray-50 rounded-lg p-3 whitespace-pre-line"
							>
								<strong>{{ __("Leave information") }}</strong
								><br />{{ doc.leave_summary }}
								<div class="text-xs text-gray-500 mt-1">
									{{ __("Only approved leave inside this invoice period is included.") }}
								</div>
							</div>
						</section>

						<section class="bg-white border rounded-xl p-5">
							<div class="flex items-center justify-between">
								<h2 class="font-semibold text-gray-900">{{ __("Adjustments") }}</h2>
								<Button v-if="canHREdit" variant="outline" @click="addAdjustment">{{
									__("Add")
								}}</Button>
							</div>
							<div v-if="form.adjustments.length" class="space-y-3 mt-4">
								<div
									v-for="(row, index) in form.adjustments"
									:key="index"
									class="grid md:grid-cols-[1.2fr_.9fr_.6fr_1fr_2fr_auto] gap-2 items-end border rounded-lg p-3"
								>
									<Field label="Type"
										><select v-model="row.adjustment_type" :disabled="!canHREdit" class="field">
											<option v-for="type in adjustmentTypes" :key="type">{{ type }}</option>
										</select></Field
									><Field label="Effect"
										><select
											v-model="row.effect"
											:disabled="!canHREdit || row.adjustment_type !== 'Other'"
											class="field"
										>
											<option>Addition</option>
											<option>Deduction</option>
										</select></Field
									><Field label="Quantity"
										><input
											v-model.number="row.quantity"
											:disabled="!canHREdit"
											type="number"
											min="0.01"
											step="0.01"
											class="field" /></Field
									><Field label="Unit amount"
										><input
											v-model.number="row.unit_amount"
											:disabled="!canHREdit"
											type="number"
											min="0"
											step="0.01"
											class="field" /></Field
									><Field label="Reason"
										><input v-model="row.note" :disabled="!canHREdit" class="field" /></Field
									><Button
										v-if="canHREdit"
										variant="ghost"
										@click="form.adjustments.splice(index, 1)"
										><FeatherIcon name="trash-2" class="w-4"
									/></Button>
								</div>
							</div>
							<div v-else class="text-sm text-gray-500 mt-4">{{ __("No adjustments") }}</div>
							<div class="mt-4 grid md:grid-cols-3 gap-3 text-sm">
								<Row label="Additions" :value="money(doc.total_additions)" /><Row
									label="Deductions"
									:value="money(doc.total_deductions)"
								/><Row label="Total" :value="money(doc.grand_total)" />
							</div>
						</section>

						<div class="flex flex-wrap justify-end gap-2 pb-8">
							<Button v-if="canEdit" variant="outline" :loading="saving" @click="saveEmployee">{{
								__("Save and recalculate")
							}}</Button>
							<Button
								v-if="canConfirm"
								variant="solid"
								:loading="saving"
								@click="confirmEmployee"
								>{{
									doc.status === "Pending Employee Confirmation"
										? __("Confirm changes")
										: __("Confirm and send to HR")
								}}</Button
							>
							<Button v-if="canHREdit" variant="outline" :loading="saving" @click="saveHR">{{
								__("Save HR changes")
							}}</Button>
							<Button
								v-if="
									isHR &&
									['Pending HR Review', 'Pending Employee Confirmation'].includes(doc.status)
								"
								variant="outline"
								theme="red"
								@click="returnInvoice"
								>{{ __("Return to employee") }}</Button
							>
							<Button
								v-if="isHR && doc.status === 'Pending HR Review'"
								variant="solid"
								:loading="saving"
								@click="approveInvoice"
								>{{ __("Approve for payment") }}</Button
							>
							<Button
								v-if="isHR && doc.status === 'Approved for Payment'"
								variant="solid"
								:loading="saving"
								@click="markPaid"
								>{{ __("Mark paid") }}</Button
							>
						</div>
					</template>
				</main>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { computed, h, inject, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"
import { Button, FeatherIcon, call } from "frappe-ui"

const props = defineProps({ id: { type: String, default: null } })
const __ = inject("$translate")
const user = inject("$user")
const router = useRouter()
const loading = ref(Boolean(props.id))
const saving = ref(false)
const error = ref("")
const doc = ref(null)
const newDueDate = ref(new Date().toISOString().slice(0, 10))
const form = reactive({})
const isHR = (user.data?.roles || []).some((role) =>
	["HR Manager", "HR User", "System Manager", "Administrator"].includes(role)
)
const paymentMethods = [
	"Bank Transfer",
	"Cash",
	"Online Payment Service",
	"Cryptocurrency",
	"Other",
]
const adjustmentTypes = [
	"Bonus",
	"Commission",
	"Paid Leave Adjustment",
	"Prepayment",
	"Deduction",
	"Other",
]
const editableFields = [
	"due_date",
	"period_start",
	"period_end",
	"due_hours",
	"payee_name",
	"payee_address",
	"preferred_payment_method",
	"payment_details",
	"bank_name",
	"bank_account_no",
	"iban",
	"employee_note",
]

const Field = (props, { slots }) =>
	h("label", { class: "block text-sm" }, [
		h("span", { class: "block text-xs font-medium text-gray-600 mb-1" }, __(props.label)),
		slots.default?.(),
	])
const Row = (props) =>
	h("div", { class: "flex items-center justify-between gap-3" }, [
		h("span", { class: "text-sm text-gray-500" }, __(props.label)),
		h("span", { class: "text-sm font-medium text-gray-900" }, props.value || "—"),
	])
Field.props = ["label"]
Row.props = ["label", "value"]

const canEdit = computed(() => Boolean(doc.value?.can_employee_edit))
const canConfirm = computed(
	() =>
		doc.value?.is_employee_owner &&
		["Draft", "Changes Requested", "Pending Employee Confirmation"].includes(doc.value.status)
)
const canHREdit = computed(
	() =>
		isHR &&
		doc.value &&
		["Pending HR Review", "Pending Employee Confirmation"].includes(doc.value.status)
)
const effectiveEdit = computed(() => canEdit.value || canHREdit.value)
const pdfUrl = computed(
	() =>
		`/api/method/frappe.utils.print_format.download_pdf?doctype=Employee%20Invoice&name=${encodeURIComponent(
			doc.value.name
		)}&format=Employee%20Invoice&no_letterhead=1`
)

function money(value) {
	return `${Number(value || 0).toFixed(2)} ${doc.value?.currency || ""}`
}
function fillForm(value) {
	doc.value = value
	Object.assign(form, value)
	form.adjustments = (value.adjustments || []).map((row) => ({ ...row }))
}
function message(err) {
	return err?.messages?.[0] || err?.message || String(err)
}
async function run(action) {
	saving.value = true
	error.value = ""
	try {
		return await action()
	} catch (err) {
		error.value = message(err)
		throw err
	} finally {
		saving.value = false
	}
}

async function createInvoice() {
	const result = await run(() =>
		call("hrms.api.employee_invoice.create_employee_invoice", { due_date: newDueDate.value })
	)
	router.replace({ name: "EmployeeInvoiceDetailView", params: { id: result.name } })
}
async function saveEmployee() {
	const values = Object.fromEntries(editableFields.map((field) => [field, form[field]]))
	fillForm(
		await run(() =>
			call("hrms.api.employee_invoice.save_employee_invoice", { name: doc.value.name, values })
		)
	)
}
async function confirmEmployee() {
	fillForm(
		await run(() =>
			call("hrms.api.employee_invoice.confirm_employee_invoice", { name: doc.value.name })
		)
	)
}
function addAdjustment() {
	form.adjustments.push({
		adjustment_type: "Bonus",
		effect: "Addition",
		quantity: 1,
		unit_amount: 0,
		note: "",
	})
}
async function saveHR() {
	const reason = window.prompt(__("Reason for these changes"))
	if (!reason) return
	const values = Object.fromEntries(
		[...editableFields, "monthly_amount", "hourly_rate", "currency", "hr_note"].map((field) => [
			field,
			form[field],
		])
	)
	values.adjustments = form.adjustments
	fillForm(
		await run(() =>
			call("hrms.api.employee_invoice.hr_update_employee_invoice", {
				name: doc.value.name,
				values,
				reason,
			})
		)
	)
}
async function returnInvoice() {
	const reason = window.prompt(__("What should the employee change?"))
	if (!reason) return
	fillForm(
		await run(() =>
			call("hrms.api.employee_invoice.hr_return_employee_invoice", {
				name: doc.value.name,
				reason,
			})
		)
	)
}
async function approveInvoice() {
	const result = await run(() =>
		call("hrms.api.employee_invoice.hr_approve_employee_invoice", { name: doc.value.name })
	)
	fillForm(result.invoice)
}
async function markPaid() {
	const payment_method = window.prompt(__("Payment method"), doc.value.preferred_payment_method)
	if (!payment_method) return
	const payment_date = window.prompt(__("Payment date"), new Date().toISOString().slice(0, 10))
	if (!payment_date) return
	const payment_reference = window.prompt(__("Payment or receipt reference"))
	if (!payment_reference) return
	fillForm(
		await run(() =>
			call("hrms.api.employee_invoice.mark_employee_invoice_paid", {
				name: doc.value.name,
				payment_method,
				payment_date,
				payment_reference,
			})
		)
	)
}

onMounted(async () => {
	if (!props.id) return
	try {
		fillForm(await call("hrms.api.employee_invoice.get_employee_invoice", { name: props.id }))
	} catch (err) {
		error.value = message(err)
	} finally {
		loading.value = false
	}
})
</script>

<style scoped>
.field {
	@apply w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 disabled:bg-gray-50 disabled:text-gray-500;
}
</style>
