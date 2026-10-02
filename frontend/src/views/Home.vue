<template>
	<BaseLayout>
		<template #body>
			<div class="p-4 md:p-6 flex flex-col gap-6">
				<!-- Charts first, then quick menu: glanceable status on top,
				     actions one scroll away on every screen size. -->
				<WorkingHoursDashboard />

				<!-- Single review entry for project leads (replaces the hidden
				     sidebar item): opens the per-section review flow. Shown
				     whenever there is anything to see — pending items get the
				     amber treatment, otherwise a neutral all-caught-up card so
				     the page is never unreachable. -->
				<router-link
					v-if="showReviewCard"
					:to="{ name: 'ProjectTimesheets' }"
					class="rounded-xl p-4 flex items-center justify-between gap-3 border"
					:class="
						pendingReviewCount > 0
							? 'bg-amber-50 border-amber-200'
							: 'bg-white border-gray-200'
					"
				>
					<div class="min-w-0">
						<div
							class="font-semibold"
							:class="pendingReviewCount > 0 ? 'text-amber-900' : 'text-gray-800'"
						>
							{{ pendingReviewCount > 0 ? __("Team hours to review") : __("Team hours") }}
						</div>
						<div
							class="text-sm mt-1"
							:class="pendingReviewCount > 0 ? 'text-amber-700' : 'text-gray-500'"
						>
							{{
								pendingReviewCount > 0
									? __("Team members submitted hours on your projects")
									: __("Nothing waiting for review")
							}}
						</div>
						<div v-if="pendingReviewCount > 0" class="text-xs font-medium text-amber-600 mt-1">
							{{ __("{0} waiting", [pendingReviewCount]) }}
						</div>
					</div>
					<FeatherIcon
						name="chevron-right"
						class="h-5 w-5 shrink-0"
						:class="pendingReviewCount > 0 ? 'text-amber-700' : 'text-gray-400'"
					/>
				</router-link>

				<!-- Mobile: Meetings first, then Quick Links -->
				<div class="md:hidden flex flex-col">
					<QuickLinks :items="meetingLinks" :title="__('Meetings')" />
					<QuickLinks :items="quickLinks" :title="__('Quick Links')" />
				</div>

				<RequestPanel />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, markRaw, computed, watch } from "vue"
import { createResource, FeatherIcon } from "frappe-ui"

import QuickLinks from "@/components/QuickLinks.vue"
import BaseLayout from "@/components/BaseLayout.vue"
import RequestPanel from "@/components/RequestPanel.vue"
import WorkingHoursDashboard from "@/components/WorkingHoursDashboard.vue"
import LeaveIcon from "@/components/icons/LeaveIcon.vue"
import ExpenseIcon from "@/components/icons/ExpenseIcon.vue"
import EmployeeAdvanceIcon from "@/components/icons/EmployeeAdvanceIcon.vue"
import SalaryIcon from "@/components/icons/SalaryIcon.vue"
import TimesheetIcon from "@/components/icons/TimesheetIcon.vue"
import TimerIcon from "@/components/icons/TimerIcon.vue"
import HolidayIcon from "@/components/icons/HolidayIcon.vue"
import ScheduleIcon from "@/components/icons/ScheduleIcon.vue"
import AvailabilityIcon from "@/components/icons/AvailabilityIcon.vue"
import DocsIcon from "@/components/icons/DocsIcon.vue"
import MeetingIcon from "@/components/icons/MeetingIcon.vue"

const __ = inject("$translate")

// Fetch current user roles to conditionally show HR links
const userInfo = createResource({
	url: "hrms.api.get_current_user_info",
	auto: true,
})

const isHR = computed(() => {
	const roles = userInfo.data?.roles || []
	return roles.some((r) =>
		["HR Manager", "HR User", "System Manager", "Administrator"].includes(r)
	)
})

const isProjectLead = computed(() => Boolean(userInfo.data?.has_led_projects))

// Single review entry: leads with pending team hours get one card that opens
// the per-section review flow (ProjectTimesheets). Hidden otherwise.
const reviewQueue = createResource({
	url: "hrms.api.weekly_timesheet.get_project_review_queue",
	auto: false,
})
const pendingReviewCount = computed(
	() => (reviewQueue.data || []).filter((row) => row.actionable).length
)
// The page must stay reachable even with zero actionable items (returned /
// draft sections still need to be visible) — otherwise leads lose the only
// entry point exactly when everything was returned.
const showReviewCard = computed(
	() => isProjectLead.value && (reviewQueue.data || []).length > 0
)

watch(
	() => userInfo.data?.has_led_projects,
	(isLead) => {
		if (isLead) reviewQueue.fetch()
	},
	{ immediate: true }
)

const quickLinks = computed(() => {
	const links = [
		{
			icon: markRaw(TimerIcon),
			title: __("Start Timer"),
			route: "TimesheetTimer",
		},
		{
			icon: markRaw(TimesheetIcon),
			title: __("My Timesheets"),
			route: "TimesheetListView",
		},
		{
			icon: markRaw(LeaveIcon),
			title: __("Request Leave"),
			route: "LeaveApplicationFormView",
		},
		{
			icon: markRaw(HolidayIcon),
			title: __("My Holidays"),
			route: "MyHolidays",
		},
		{
			icon: markRaw(ScheduleIcon),
			title: __("My Schedule"),
			route: "MySchedule",
		},
		{
			icon: markRaw(AvailabilityIcon),
			title: __("Team Availability"),
			route: "Availability",
		},
		{
			icon: markRaw(ExpenseIcon),
			title: __("Claim an Expense"),
			route: "ExpenseClaimFormView",
		},
		{
			icon: markRaw(EmployeeAdvanceIcon),
			title: __("Request an Advance"),
			route: "EmployeeAdvanceFormView",
		},
		{
			icon: markRaw(SalaryIcon),
			title: __("Invoices"),
			route: "InvoicesDashboard",
		},
		{
			icon: markRaw(DocsIcon),
			title: __("Documents"),
			route: "Docs",
		},
	]

	if (isHR.value) {
		links.push(
			{
				icon: markRaw(HolidayIcon),
				title: __("Holiday Approvals"),
				route: "HolidayApprovals",
			},
			{
				icon: markRaw(ScheduleIcon),
				title: __("Schedule Approvals"),
				route: "ScheduleApprovals",
			}
		)
	}

	return links
})

const meetingLinks = computed(() => [
	{
		icon: markRaw(MeetingIcon),
		title: __("Meeting Finder"),
		route: "MeetingFinder",
	},
])
</script>
