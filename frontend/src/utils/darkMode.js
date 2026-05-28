import { ref, watchEffect } from "vue"

const STORAGE_KEY = "hrms-dark-mode"

// Singleton state — shared across all useDarkMode() calls
const isDark = ref(
	localStorage.getItem(STORAGE_KEY)
		? localStorage.getItem(STORAGE_KEY) === "true"
		: window.matchMedia("(prefers-color-scheme: dark)").matches
)

function applyDarkMode(dark) {
	const html = document.documentElement
	if (dark) {
		html.classList.add("dark", "ion-palette-dark")
	} else {
		html.classList.remove("dark", "ion-palette-dark")
	}
	localStorage.setItem(STORAGE_KEY, dark)
}

// Apply immediately on module load (before Vue mounts, prevents flash)
applyDarkMode(isDark.value)

export function useDarkMode() {
	watchEffect(() => applyDarkMode(isDark.value))

	return {
		isDark,
		toggleDarkMode() { isDark.value = !isDark.value },
	}
}
