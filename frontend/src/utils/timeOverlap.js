export const MAX_OVERLAP_MS = 5 * 60 * 1000

function timestamp(value) {
	const text = String(value || "").replace(" ", "T")
	// These are system-local wall times, not instants in the device's timezone.
	return Date.parse(text + (/(Z|[+-]\d{2}:\d{2})$/.test(text) ? "" : "Z"))
}

export function overlapMilliseconds(log, others) {
	const start = timestamp(log.from_time), end = timestamp(log.to_time)
	if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return 0
	const intervals = others.map(row => [Math.max(start, timestamp(row.from_time)), Math.min(end, timestamp(row.to_time))])
		.filter(([left, right]) => Number.isFinite(left) && Number.isFinite(right) && right > left)
		.sort((a, b) => a[0] - b[0] || a[1] - b[1])
	let total = 0, boundary = start
	for (const [left, right] of intervals) {
		if (right > boundary) { total += right - Math.max(left, boundary); boundary = right }
	}
	return total
}
