import { createDocumentResource } from "frappe-ui"

import dayjs from "@/utils/dayjs"

const settings = createDocumentResource({
	doctype: "System Settings",
	name: "System Settings",
	auto: false,
})

export const formatCurrency = (value, currency) => {
	if (!currency) return value

	// hack: if value contains a space, it is already formatted
	if (value?.toString().trim().includes(" ")) return value

	const locale = settings.doc?.country == "India" ? "en-IN" : settings.doc?.language

	const formatter = Intl.NumberFormat(locale, {
		style: "currency",
		currency: currency,
		trailingZeroDisplay: "stripIfInteger",
		currencyDisplay: "narrowSymbol",
	})
	return (
		formatter
			.format(value)
			// add space between the digits and symbol
			.replace(/^(\D+)/, "$1 ")
			// remove extra spaces if any (added by some browsers)
			.replace(/\s+/, " ")
	)
}

/**
 * Format decimal hours as H:MM ("42.7" → "42:42"). Used everywhere durations
 * are displayed instead of raw decimals.
 */
export const formatHours = (hours) => {
	const totalMinutes = Math.round(Number(hours || 0) * 60)
	const h = Math.floor(totalMinutes / 60)
	const m = totalMinutes % 60
	return `${h}:${String(m).padStart(2, "0")}`
}

export const formatTimestamp = (timestamp) => {
	const formattedTime = dayjs(timestamp).format("hh:mm a")

	if (dayjs(timestamp).isToday()) return formattedTime
	else if (dayjs(timestamp).isYesterday()) return `${formattedTime} yesterday`
	else if (dayjs(timestamp).isSame(dayjs(), "year"))
		return `${formattedTime} on ${dayjs(timestamp).format("D MMM")}`

	return `${formattedTime} on ${dayjs(timestamp).format("D MMM, YYYY")}`
}
