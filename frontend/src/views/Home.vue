<template>
	<BaseLayout>
		<template #body>
			<div class="p-4 md:p-6 flex flex-col gap-6">
				<!-- Charts first, then quick menu: glanceable status on top,
				     actions one scroll away on every screen size. -->
				<WorkingHoursDashboard />

				<!-- Single review entry for project leads (replaces the hidden
				     sidebar item): opens the per-section review flow. -->
				<router-link
					v-if="showReviewCard"
					:to="{ name: 'ProjectTimesheets' }"
					class="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between gap-3"
				>
					<div class="min-w-0">
						<div class="font-semibold text-amber-900">{{ __("Team hours to review") }}</div>
						<div class="text-sm text-amber-700 mt-1">
							{{ __("Team members submitted hours on your projects") }}
						</div>
						<div class="text-xs font-medium text-amber-600 mt-1">
							{{ __("{0} waiting", [pendingReviewCount]) }}
						</div>
					</div>
					<FeatherIcon name="chevron-right" class="h-5 w-5 text-amber-700 shrink-0" />
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

const isProjectLead = computed(() => Boolean(userInfo.data?.is_project_lead))

// Single review entry: leads with pending team hours get one card that opens
// the per-section review flow (ProjectTimesheets). Hidden otherwise.
const reviewQueue = createResource({
	url: "hrms.api.weekly_timesheet.get_project_review_queue",
	auto: false,
})
const pendingReviewCount = computed(
	() => (reviewQueue.data || []).filter((row) => row.actionable).length
)
const showReviewCard = computed(() => isProjectLead.value && pendingReviewCount.value > 0)

watch(
	() => userInfo.data?.is_project_lead,
	(isLead) => {
		if (isLead) reviewQueue.fetch()
	},
	{ immediate: true }
)

const mySchedule = createResource({
	url: "hrms.api.get_my_schedule",
	params: { year: String(new Date().getFullYear()) },
	auto: true,
})
const hideMainScheduleLink = computed(() => mySchedule.data?.status === "Approved")

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
		...(!hideMainScheduleLink.value
			? [
					{
						icon: markRaw(ScheduleIcon),
						title: __("My Schedule"),
						route: "MySchedule",
					},
			  ]
			: []),
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
