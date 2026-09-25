/**
 * Server datetimes arrive naive ("YYYY-MM-DD HH:mm:ss") in the SITE'S time
 * zone (System Settings > Time Zone), but dayjs() reads naive strings as
 * browser-local. On any browser outside the server zone that skews every
 * relative timestamp (e.g. +9h for a GMT+4 viewer on an EST server).
 *
 * SERVER_TZ_OFFSET must match System Settings > Time Zone. EST is a fixed
 * UTC-5 zone (no DST), so a constant offset is exact, not approximate.
 * If the site ever moves zones, update this single constant.
 */
export const SERVER_TZ_OFFSET = "-05:00"

/** Parse a naive server datetime string into the correct absolute instant. */
export function parseServerTime(dayjs, value) {
	if (!value) return null
	const str = String(value)
	if (/([+-]\d{2}:?\d{2}|Z)$/.test(str)) return dayjs(str)
	return dayjs(str.replace(" ", "T") + SERVER_TZ_OFFSET)
}

/** Relative label ("2 hours ago") correct in any browser timezone. */
export function timeAgo(dayjs, value) {
	const parsed = parseServerTime(dayjs, value)
	if (!parsed || !parsed.isValid()) return ""
	return parsed.fromNow()
}
