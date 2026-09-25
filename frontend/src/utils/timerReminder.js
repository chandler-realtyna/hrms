/**
 * Shared long-running-timer reminder logic (framework-free so it is unit-testable).
 *
 * Background: the 2h reminder used to live only as a setTimeout inside the
 * Timer page. Any navigation away unmounted the page and silently cancelled
 * it, so users who start a timer and work elsewhere never got notified.
 * A global checker (see useTimerReminder.js, mounted in App.vue) now watches
 * the persisted timer state from anywhere in the app.
 */

export const TIMER_STORAGE_KEY = "hrms_active_timer"
export const TIMER_NOTIFIED_KEY = "hrms_timer_notified_start"
export const LONG_RUNNING_MS = 2 * 60 * 60 * 1000

/**
 * Decide whether a long-running notification should fire.
 * Pure function over plain values — covered by unit tests.
 *
 * @param {object} args
 * @param {boolean} args.running        timer currently recording (has startTime)
 * @param {number} args.elapsedMs       ms since startTime
 * @param {string|null} args.notifiedStart  startTime already notified for (if any)
 * @param {string} args.startTime       current timer startTime (ISO)
 */
export function shouldNotify({ running, elapsedMs, notifiedStart, startTime }) {
	if (!running || !startTime) return false
	if (!Number.isFinite(elapsedMs) || elapsedMs < LONG_RUNNING_MS) return false
	if (notifiedStart && notifiedStart === startTime) return false
	return true
}
