<template>
	<BaseLayout>
		<template #body>
			<div class="flex flex-col items-center my-7 p-4 gap-7">
				<QuickLinks :items="quickLinks" :title="__('Quick Links')" />
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
			title: __("View Salary Slips"),
			route: "SalarySlipsDashboard",
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
</script>
