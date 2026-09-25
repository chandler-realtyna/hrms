import { onMounted, onUnmounted, inject } from "vue"
import { call, toast } from "frappe-ui"

import { unreadNotificationsCount } from "@/data/notifications"

import {
	TIMER_STORAGE_KEY,
	TIMER_NOTIFIED_KEY,
	shouldNotify,
} from "@/utils/timerReminder.js"

export { TIMER_NOTIFIED_KEY }

function readTimerState() {
	try {
		const raw = localStorage.getItem(TIMER_STORAGE_KEY)
		if (!raw) return null
		const state = JSON.parse(raw)
		if (!state?.startTime) return null
		return state
	} catch {
		return null
	}
}

/**
 * Global long-running timer watchdog. Mount once (App.vue): checks the
 * persisted timer every minute and whenever the tab becomes visible, so the
 * 2-hour reminder fires no matter which page the user is on.
 * Exactly-once per timer start via TIMER_NOTIFIED_KEY (shared with Timer.vue).
 */
export function useTimerReminder() {
	const employee = inject("$employee", null)
	const __ = inject("$translate", (s) => s)

	let interval = null

	async function check() {
		try {
			const state = readTimerState()
			if (!state) return
			const elapsedMs = Date.now() - new Date(state.startTime).getTime()
			const notifiedStart = localStorage.getItem(TIMER_NOTIFIED_KEY)
			if (
				!shouldNotify({
					running: true,
					elapsedMs,
					notifiedStart,
					startTime: state.startTime,
				})
			) {
				return
			}
			const emp = employee?.data?.name
			if (!emp) return
			await call("hrms.api.notify_long_running_timer", {
				employee: emp,
				project: state.form?.project || "",
				started_at: state.startTime,
			})
			localStorage.setItem(TIMER_NOTIFIED_KEY, state.startTime)
			unreadNotificationsCount.reload().catch(() => {})
			toast({
				title: __("This timer has been running for over two hours. You may have forgotten to save it."),
				icon: "alert-circle",
				iconClasses: "text-amber-500",
			})
		} catch (err) {
			// Reminder must never break the app, but never fail silently either.
			console.warn("Timer reminder check failed:", err)
		}
	}

	onMounted(() => {
		check()
		interval = setInterval(check, 60 * 1000)
		document.addEventListener("visibilitychange", check)
	})

	onUnmounted(() => {
		if (interval) clearInterval(interval)
		document.removeEventListener("visibilitychange", check)
	})
}
