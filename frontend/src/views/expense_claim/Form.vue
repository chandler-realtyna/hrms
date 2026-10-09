<template>
	<ion-page>
		<ion-content :fullscreen="true">
			<FormView
				v-if="formFields.data"
				doctype="Expense Claim"
				v-model="expenseClaim"
				:isSubmittable="true"
				:fields="formFields.data"
				:id="props.id"
				:showAttachmentView="true"
				@validateForm="validateForm"
				:showDownloadPDFButton="true"
				@formReloaded="onFormReloaded"
			>
				<!-- Child Tables -->
				<template #expenses="{ isFormReadOnly }">
					<ExpensesTable
						v-model:expenseClaim="expenseClaim"
						:isReadOnly="isReadOnly || isFormReadOnly"
						@addExpenseItem="addExpenseItem"
						@updateExpenseItem="updateExpenseItem"
						@deleteExpenseItem="deleteExpenseItem"
					/>
				</template>

				<!-- Rarely needed: collapsed unless taxes already exist -->
				<template #taxes="{ isFormReadOnly }">
					<details :open="!!expenseClaim.taxes?.length" class="rounded-xl border bg-white">
						<summary class="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-gray-700 flex items-center justify-between">
							{{ __("Taxes & Charges (optional)") }}
							<span class="text-xs font-normal text-gray-400">
								{{ expenseClaim.taxes?.length ? __("Added") : __("Add if needed") }}
							</span>
						</summary>
						<div class="px-4 pb-4">
							<ExpenseTaxesTable
								v-model:expenseClaim="expenseClaim"
								:isReadOnly="isReadOnly || isFormReadOnly"
								@addExpenseTax="addExpenseTax"
								@updateExpenseTax="updateExpenseTax"
								@deleteExpenseTax="deleteExpenseTax"
							/>
						</div>
					</details>
				</template>

				<template #advances="{ isFormReadOnly }" v-if="expenseClaim.advances?.length">
					<ExpenseAdvancesTable
						v-model:expenseClaim="expenseClaim"
						:isReadOnly="isReadOnly || isFormReadOnly"
					/>
				</template>
			</FormView>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonPage, IonContent } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { computed, ref, watch, inject } from "vue"

import FormView from "@/components/FormView.vue"
import ExpensesTable from "@/components/ExpensesTable.vue"
import ExpenseTaxesTable from "@/components/ExpenseTaxesTable.vue"
import ExpenseAdvancesTable from "@/components/ExpenseAdvancesTable.vue"
import { getCompanyCurrency } from "@/data/currencies"
import { useCurrencyConversion } from "@/composables/useCurrencyConversion"


const dayjs = inject("$dayjs")

const today = dayjs().format("YYYY-MM-DD")
const isReadOnly = ref(false)

const sessionEmployee = inject("$employee")
const currEmployee = ref(sessionEmployee.data.name)
const employeeCompany = ref(sessionEmployee.data.company)


const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})

// NOTE: no tab navigation — the form renders as one scrollable page
// (main fields → expenses → optional taxes → advances → totals) since
// advances/totals are auto-managed and don't need separate tabs.

// object to store form data
const expenseClaim = ref({
	employee: currEmployee,
	company: employeeCompany,
	doctype: "Expense Claim",
})

const companyCurrency = computed(() => getCompanyCurrency(expenseClaim.value.company))

// get form fields
const formFields = createResource({
	url: "hrms.api.get_doctype_fields",
	params: { doctype: "Expense Claim" },
	transform(data) {
		let fields = getFilteredFields(data)

		return fields.map((field) => {
			if (field.fieldname === "posting_date") field.default = today
			return applyFilters(field)
		})
	},
	onSuccess(_data) {
		expenseApproverDetails.reload()
		if (!expenseClaim.value.currency) {
			employeeCurrency.reload()
		}
		companyDetails.reload()
	},
})
formFields.reload()

useCurrencyConversion(
	formFields,
	expenseClaim,
	[
		"total_sanctioned_amount",
		"total_taxes_and_charges",
		"total_advance_amount",
		"grand_total",
		"total_claimed_amount"
	]
)

// resources & helper functions
const advances = createResource({
	url: "hrms.hr.doctype.expense_claim.expense_claim.get_advances",
	makeParams() {
		return { expense_claim: expenseClaim.value }
	},
	onSuccess(data) {
		selectAllocatedAdvances()
		addUnallocatedAdvances(data)
	},
})

function selectAllocatedAdvances() {
	if (props.id) {
		expenseClaim.value?.advances?.map((advance) => (advance.selected = true))
	} else {
		expenseClaim.value.advances = []
	}
}

function addUnallocatedAdvances(data) {
	// only show advances for selection in a draft claim
	const isDraft = expenseClaim.value?.docstatus == 0 || !expenseClaim.value?.docstatus
	if (!isDraft) return

	const allocatedAdvances = new Set(
		expenseClaim.value?.advances?.map((advance) => advance.employee_advance)
	)

	return data.forEach((advance) => {
		if (props.id && allocatedAdvances.has(advance.employee_advance)) return

		expenseClaim.value?.advances?.push({
			...advance,
			selected: false,
			allocated_amount: 0,
		})
	})
}

function onFormReloaded() {
	advances.reload()
}

const expenseApproverDetails = createResource({
	url: "hrms.api.get_expense_approval_details",
	params: { employee: currEmployee.value },
	onSuccess(data) {
		setExpenseApprover(data)
	},
})

const employeeCurrency = createResource({
	url: "frappe.client.get_value",
	makeParams() {
		return {
			doctype: "Employee",
			fieldname: ["salary_currency"],
			filters: { name: currEmployee.value },
		};
	},
	onSuccess(data) {
		if (data?.salary_currency) {
			expenseClaim.value.currency = data.salary_currency;
		}
	}
});

const companyDetails = createResource({
	url: "hrms.api.get_company_cost_center_and_expense_account",
	params: { company: expenseClaim.value.company },
	onSuccess(data) {
		expenseClaim.value.cost_center = data?.cost_center
		expenseClaim.value.payable_account =
			data?.default_expense_claim_payable_account
	},
})

const exchangeRate = createResource({
	url: "erpnext.setup.utils.get_exchange_rate",
	onSuccess(data) {
		expenseClaim.value.exchange_rate = data
	},
})

// form scripts
watch(
	() => expenseClaim.value.employee,
	(employee_id) => {
		if (props.id && employee_id !== currEmployee.value) {
			// if employee is not the current user, set form as read only
			setFormReadOnly()
		}
		currEmployee.value = employee_id
		expenseApproverDetails.fetch({ employee: currEmployee.value })
		employeeCurrency.fetch()
	},
)

watch(
	() => expenseClaim.value.company,
	(company) => {
		employeeCompany.value = company
		companyDetails.fetch({ company: employeeCompany.value })
	}
)

watch(
	() => expenseClaim.value.currency,
	() => setExchangeRate()
)

watch(companyCurrency, () => setExchangeRate())

// Advance totals are only relevant when advances exist.
watch(
	() => expenseClaim.value.advances?.length,
	(n) => {
		const totalAdvance = formFields.data?.find(
			(field) => field.fieldname === "total_advance_amount"
		)
		if (totalAdvance) totalAdvance.hidden = !n ? 1 : 0
	},
	{ immediate: true }
)

watch(
	() => expenseClaim.value.name,
	() => {
		advances.reload()
	},
	{ immediate: true }
)

watch(
	() => expenseClaim.value.advances,
	(_value) => {
		calculateTotalAdvance()
	},
	{ deep: true }
)

watch(
	() => expenseClaim.value.cost_center,
	() => {
		expenseClaim?.value?.expenses?.forEach((expense) => {
			expense.cost_center = expenseClaim.value.cost_center
		})
	}
)

// helper functions
function getFilteredFields(fields) {
	// Minimal claim form: only what the employee must provide or review.
	// Everything accounting-related is auto-set (cost center, payable
	// account, posting date) or irrelevant day-to-day, so it stays hidden
	// instead of overwhelming the page.
	const excludeFields = [
		"naming_series",
		"task",
		"taxes_and_charges_sb",
		"advance_payments_sb",
		// hidden sections + their fields
		"currency_section",
		"expense_details",
		"transactions_section",
		"gain_loss_section",
		"accounting_details",
		"accounting_dimensions_section",
		"more_details",
		"base_total_sanctioned_amount",
		"base_total_advance_amount",
		"base_grand_total",
		"base_total_claimed_amount",
		"base_total_taxes_and_charges",
		"total_amount_reimbursed",
		"total_sanctioned_amount",
		"total_taxes_and_charges",
		"total_exchange_gain_loss",
		"gain_loss_account",
		"posting_date",
		"is_paid",
		"mode_of_payment",
		"bank_or_cash_account",
		"payable_account",
		"clearance_date",
		"project",
		"cost_center",
		"status",
		"delivery_trip",
		"vehicle_log",
	]
	const extraFields = [
		"employee",
		"employee_name",
		"department",
		"company",
		"remark",
		"is_paid",
		"mode_of_payment",
		"clearance_date",
		"approval_status",
	]

	if (!props.id) excludeFields.push(...extraFields)

	return fields.filter((field) => {
		if (excludeFields.includes(field.fieldname)) return false

		if (field.fieldname?.startsWith("base_")) return false
		return true
	})
}

function applyFilters(field) {
	if (["employee", "employee_name", "company"].includes(field.fieldname)) {
		field.read_only = 1
	}
	if (field.fieldname === "payable_account") {
		field.linkFilters = {
			report_type: "Balance Sheet",
			account_type: "Payable",
			company: expenseClaim.value.company,
			is_group: 0,
			account_currency: expenseClaim.value.currency,
		}
	} else if (field.fieldname === "cost_center") {
		field.linkFilters = {
			company: expenseClaim.value.company,
			is_group: 0,
		}
	} else if (field.fieldname === "project") {
		field.linkFilters = {
			company: expenseClaim.value.company,
		}
	}

	return field
}

function setExpenseApprover(data) {
	const expense_approver = formFields.data?.find(
		(field) => field.fieldname === "expense_approver"
	)
	expense_approver.reqd = data?.is_mandatory
	expense_approver.documentList = data?.department_approvers.map(
		(approver) => ({
			label: approver.full_name
				? `${approver.name} : ${approver.full_name}`
				: approver.name,
			value: approver.name,
		})
	)

	expenseClaim.value.expense_approver = data?.expense_approver
	expenseClaim.value.expense_approver_name = data?.expense_approver_name
}

function addExpenseItem(item) {
	if (!expenseClaim.value.expenses) expenseClaim.value.expenses = []
	expenseClaim.value.expenses.push(item)
	calculateTotals()
	calculateTaxes()
	allocateAdvanceAmount()
}

function updateExpenseItem(item, idx) {
	expenseClaim.value.expenses[idx] = item
	calculateTotals()
	calculateTaxes()
	allocateAdvanceAmount()
}

function deleteExpenseItem(idx) {
	expenseClaim.value.expenses.splice(idx, 1)
	calculateTotals()
	calculateTaxes()
	allocateAdvanceAmount()
}

function addExpenseTax(item) {
	if (!expenseClaim.value.taxes) expenseClaim.value.taxes = []
	expenseClaim.value.taxes.push(item)
	calculateTaxes()
	allocateAdvanceAmount()
}

function updateExpenseTax(item, idx) {
	expenseClaim.value.taxes[idx] = item
	calculateTaxes()
	allocateAdvanceAmount()
}

function deleteExpenseTax(idx) {
	expenseClaim.value.taxes.splice(idx, 1)
	calculateTaxes()
	allocateAdvanceAmount()
}

function calculateTotals() {
	let total_claimed_amount = 0
	let total_sanctioned_amount = 0

	expenseClaim.value?.expenses?.forEach((item) => {
		total_claimed_amount += parseFloat(item.amount)
		total_sanctioned_amount += parseFloat(item.sanctioned_amount)
	})

	expenseClaim.value.total_claimed_amount = total_claimed_amount
	expenseClaim.value.total_sanctioned_amount = total_sanctioned_amount
	calculateGrandTotal()
}

function calculateTaxes() {
	let total_taxes_and_charges = 0

	expenseClaim.value?.taxes?.forEach((item) => {
		if (item.rate) {
			item.tax_amount =
				parseFloat(expenseClaim.value.total_sanctioned_amount) *
				parseFloat(item.rate / 100)
		}

		item.total =
			parseFloat(item.tax_amount) +
			parseFloat(expenseClaim.value.total_sanctioned_amount)
		total_taxes_and_charges += parseFloat(item.tax_amount)
	})
	expenseClaim.value.total_taxes_and_charges = total_taxes_and_charges
	calculateGrandTotal()
}

function calculateGrandTotal() {
	expenseClaim.value.grand_total =
		parseFloat(expenseClaim.value.total_sanctioned_amount || 0) +
		parseFloat(expenseClaim.value.total_taxes_and_charges || 0) -
		parseFloat(expenseClaim.value.total_advance_amount || 0)
}

function allocateAdvanceAmount() {
	// allocate reqd advance amount
	let amount_to_be_allocated =
		parseFloat(expenseClaim.value.total_sanctioned_amount) +
		parseFloat(expenseClaim.value.total_taxes_and_charges)

	if (!amount_to_be_allocated) return
	let total_advance_amount = 0

	expenseClaim?.value?.advances?.forEach((advance) => {
		if (amount_to_be_allocated >= parseFloat(advance.unclaimed_amount)) {
			advance.allocated_amount = parseFloat(advance.unclaimed_amount)
			amount_to_be_allocated -= parseFloat(advance.allocated_amount)
		} else {
			advance.allocated_amount = amount_to_be_allocated
			amount_to_be_allocated = 0
		}

		advance.selected = advance.allocated_amount > 0 ? true : false
		total_advance_amount += parseFloat(advance.allocated_amount)
	})
	expenseClaim.value.total_advance_amount = total_advance_amount
	calculateGrandTotal()
}

function calculateTotalAdvance() {
	// update total advance amount as per user selection & edited values
	let total_advance_amount = 0

	expenseClaim?.value?.advances?.forEach((advance) => {
		if (advance.selected || parseFloat(advance.allocated_amount) > 0) {
			total_advance_amount += parseFloat(advance.allocated_amount || 0)
		}
	})
	expenseClaim.value.total_advance_amount = total_advance_amount
	calculateGrandTotal()
}

function setFormReadOnly() {
	if (props.id && expenseClaim.value.expense_approver !== currEmployee.value) return
	formFields.data.map((field) => (field.read_only = true))
	isReadOnly.value = true
}

function validateForm() {
	// set selected advances
	if (!expenseClaim?.value?.advances) return

	expenseClaim.value.advances = expenseClaim?.value?.advances?.filter(
		(advance) => advance.selected
	)
	expenseClaim?.value?.expenses?.forEach((expense) => {
		expense.cost_center = expenseClaim.value.cost_center
	})
}

function setExchangeRate() {
	if (!expenseClaim.value.currency || !formFields.data) return
	const exchange_rate_field = formFields.data?.find(
		(field) => field.fieldname === "exchange_rate"
	)
	if (!exchange_rate_field) return

	// Same currency as the company: rate is trivially 1, no input needed.
	if (companyCurrency.value && expenseClaim.value.currency === companyCurrency.value) {
		expenseClaim.value.exchange_rate = 1
		exchange_rate_field.hidden = 1
		return
	}

	exchangeRate.fetch({
		from_currency: expenseClaim.value.currency,
		to_currency: companyCurrency.value,
	})
	exchange_rate_field.hidden = 0
}
</script>
