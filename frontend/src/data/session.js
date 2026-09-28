import { computed, reactive } from "vue"
import { createResource, call } from "frappe-ui"
import { userResource } from "./user"
import { employeeResource } from "./employee"
import { TIMER_STORAGE_KEY, TIMER_NOTIFIED_KEY } from "@/utils/timerReminder.js"
import router from "@/router"

// Timer + prefs keys must never leak across accounts on a shared browser.
// The logout success handler wipes them below; Timer.vue additionally stamps
// saved state with the owner and ignores mismatches (belt and suspenders).
export { TIMER_STORAGE_KEY }
const FAVORITES_KEY = "hrms_favorite_projects"

export function clearLocalAccountState() {
	try {
		localStorage.removeItem(TIMER_STORAGE_KEY)
		localStorage.removeItem(TIMER_NOTIFIED_KEY)
		localStorage.removeItem(FAVORITES_KEY)
	} catch {
		// storage is best-effort; logout must never fail because of it
	}
}

export function sessionUser() {
	let cookies = new URLSearchParams(document.cookie.split("; ").join("&"))
	let _sessionUser = cookies.get("user_id")
	if (_sessionUser === "Guest") {
		_sessionUser = null
	}
	return _sessionUser
}

function handleLogin(response) {
	if (response.message === "Logged In") {
		userResource.reload()
		employeeResource.reload()

		session.user = sessionUser()
		router.replace({ path: "/" })
	}
}

export const session = reactive({
	login: async (email, password) => {
		const response = await call("login", { usr: email, pwd: password })
		handleLogin(response)
		return response
	},
	otp: async (tmp_id, otp) => {
		const response = await call("login", { tmp_id, otp })
		handleLogin(response)
		return response
	},
	logout: createResource({
		url: "logout",
		onSuccess() {
			clearLocalAccountState()
			userResource.reset()
			employeeResource.reset()

			session.user = sessionUser()
			router.replace({ name: "Login" })
			window.location.reload()
		},
	}),
	user: sessionUser(),
	isLoggedIn: computed(() => !!session.user),
})
