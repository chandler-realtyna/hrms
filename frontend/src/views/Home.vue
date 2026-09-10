<template>
	<BaseLayout>
		<template #body>
			<div class="p-4 md:p-6 flex flex-col gap-6">
				<!-- Mobile: Quick Links as card lists at the top -->
				<div class="md:hidden flex flex-col">
					<QuickLinks :items="quickLinks" :title="__('Quick Links')" />
					<QuickLinks :items="meetingLinks" :title="__('Meetings')" />
				</div>

				<WorkingHoursDashboard />
				<RequestPanel />
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, markRaw, computed } from "vue"
import { createResource } from "frappe-ui"

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

const isProjectController = computed(() => Boolean(userInfo.data?.is_project_controller))

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
		...(isProjectController.value
			? [
					{
						icon: markRaw(TimesheetIcon),
						title: __("Project Approvals"),
						route: "TimesheetProjectApprovals",
					},
			  ]
			: []),
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
