"""Measure union overlap, so intersecting records do not double-count minutes."""

MAX_OVERLAP_SECONDS = 5 * 60


def overlap_seconds(start, end, intervals):
	clipped = sorted((max(start, left), min(end, right)) for left, right in intervals
		if left < end and right > start and right > left)
	total, boundary = 0.0, start
	for left, right in clipped:
		if right > boundary:
			total += (right - max(left, boundary)).total_seconds()
			boundary = right
	return total
