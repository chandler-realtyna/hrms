/**
 * Timezone utilities — pure browser APIs, no library dependency.
 *
 * All functions work with IANA timezone names (e.g. "America/New_York",
 * "Europe/Berlin") which are also valid pytz names on the backend.
 */

/**
 * Return the viewer's IANA timezone as detected by the browser.
 * Falls back to "America/New_York" if the API is unavailable.
 */
export function getViewerTimezone() {
	try {
		return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York"
	} catch {
		return "America/New_York"
	}
}

/**
 * Return a short display label for an IANA timezone on a given date, e.g.:
 *   "America/New_York" → "EST" or "EDT"
 *   "Europe/Berlin"    → "CET" or "CEST"
 *   "Asia/Dubai"       → "GST"
 *   (some zones fall back to "GMT+3" style)
 */
export function getTimezoneAbbr(ianaName, date = new Date()) {
	try {
		const parts = Intl.DateTimeFormat("en-US", {
			timeZone: ianaName,
			timeZoneName: "short",
		}).formatToParts(date)
		return parts.find((p) => p.type === "timeZoneName")?.value ?? ianaName
	} catch {
		return ianaName
	}
}

/**
 * Return the UTC offset in whole minutes for an IANA timezone on a given date.
 * Positive = ahead of UTC (east), negative = behind UTC (west).
 *
 * Uses the "numeric" timeZoneName trick which is the most reliable approach
 * without a library:
 *   "GMT+05:30" → +330
 *   "GMT-04:00" → -240
 */
export function getUtcOffsetMinutes(ianaName, date = new Date()) {
	try {
		const label = Intl.DateTimeFormat("en-GB", {
			timeZone: ianaName,
			timeZoneName: "shortOffset",
		})
			.formatToParts(date)
			.find((p) => p.type === "timeZoneName")?.value ?? "GMT+0"

		// label looks like "GMT+5:30", "GMT-4", "GMT+0"
		const match = label.match(/GMT([+-])(\d+)(?::(\d+))?/)
		if (!match) return 0
		const sign = match[1] === "+" ? 1 : -1
		const hours = parseInt(match[2], 10)
		const mins = parseInt(match[3] ?? "0", 10)
		return sign * (hours * 60 + mins)
	} catch {
		return 0
	}
}

/**
 * Return the whole-hour offset difference between two IANA timezones.
 * Positive  → tz2 is ahead of tz1 (tz2 is further east).
 * Negative  → tz2 is behind tz1.
 * Zero      → same offset (may still be different zones but same wall clock).
 */
export function getOffsetDiffHours(tz1, tz2, date = new Date()) {
	if (!tz1 || !tz2) return 0
	const diff = (getUtcOffsetMinutes(tz2, date) - getUtcOffsetMinutes(tz1, date)) / 60
	return Math.round(diff)
}

/**
 * Format an offset difference as a human-readable chip label.
 *   +7  → "+7h ahead"
 *   -5  → "5h behind"
 *   0   → "Same timezone"
 */
export function formatOffsetDiff(hoursDiff) {
	if (hoursDiff === 0) return "Same timezone"
	if (hoursDiff > 0) return `+${hoursDiff}h ahead`
	return `${Math.abs(hoursDiff)}h behind`
}
