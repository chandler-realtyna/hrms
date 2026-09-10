<template>
	<Transition
		enter-active-class="transition duration-200 ease-out"
		enter-from-class="-translate-y-3 opacity-0"
		leave-active-class="transition duration-150 ease-in"
		leave-to-class="-translate-y-3 opacity-0"
	>
		<section
			v-if="showPrompt"
			role="region"
			aria-live="polite"
			class="pwa-install-prompt fixed left-3 right-3 z-[100] rounded-2xl border border-gray-200 bg-white p-4 shadow-xl md:left-auto md:right-5 md:w-[390px]"
			style="top: max(0.75rem, env(safe-area-inset-top))"
		>
			<div class="flex items-start gap-3">
				<div
					class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green-100 text-green-700"
				>
					<FeatherIcon :name="isIos ? 'share' : 'download'" class="h-5 w-5" />
				</div>
				<div class="min-w-0 flex-1">
					<h2 class="text-base font-semibold text-gray-900">{{ promptTitle }}</h2>
					<p class="mt-1 text-sm leading-5 text-gray-600">{{ promptMessage }}</p>
				</div>
				<button
					type="button"
					class="-mr-1 -mt-1 rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
					:aria-label="__('Not now')"
					@click="dismiss"
				>
					<FeatherIcon name="x" class="h-4 w-4" />
				</button>
			</div>

			<div class="mt-3 flex items-center justify-end gap-2">
				<Button variant="subtle" @click="dismiss">{{ __("Not now") }}</Button>
				<button
					type="button"
					class="inline-flex h-8 items-center justify-center rounded-lg bg-gray-900 px-3 text-sm font-medium text-white transition-colors hover:bg-gray-800 focus:outline-none focus-visible:ring focus-visible:ring-gray-400"
					@click="handlePrimaryAction"
				>
					{{ primaryActionLabel }}
				</button>
			</div>

			<div
				v-if="showInstructions"
				class="mt-3 rounded-xl border border-green-100 bg-green-50 px-3 py-2.5 text-sm text-gray-700"
			>
				<ol class="list-decimal space-y-1 pl-5">
					<li v-for="step in installSteps" :key="step">{{ step }}</li>
				</ol>
				<p v-if="showChromeRecovery" class="mt-2 border-t border-green-200 pt-2 text-xs leading-5">
					{{
						__(
							'If Chrome still considers HRMS installed, open "chrome://apps", remove HRMS from Chrome, then reload this page.'
						)
					}}
				</p>
			</div>
		</section>
	</Transition>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue"
import { FeatherIcon } from "frappe-ui"

const INSTALLED_KEY = "hrms:install_prompt_installed"

const deferredPrompt = shallowRef(null)
const showPrompt = ref(false)
const showInstructions = ref(false)
const dismissedThisSession = ref(false)
let showTimer

const userAgent = window.navigator.userAgent
const isIos =
	/iphone|ipad|ipod/i.test(userAgent) ||
	(window.navigator.platform === "MacIntel" && window.navigator.maxTouchPoints > 1)
const isAndroid = /android/i.test(userAgent)
const isSafari =
	/safari/i.test(userAgent) && !/chrome|crios|fxios|edgios|opr|android/i.test(userAgent)
const isMac = /macintosh|mac os x/i.test(userAgent) && !isIos
const isChromiumDesktop = /chrome|edg|opr/i.test(userAgent) && !isAndroid && !isIos

const isInstalled = () =>
	window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true

const wasMarkedInstalled = ref(
	window.localStorage.getItem(INSTALLED_KEY) === "1" && !isInstalled()
)

const canOfferInstall = () => !dismissedThisSession.value

const canInstall = computed(() => Boolean(deferredPrompt.value))
const showChromeRecovery = computed(
	() => showInstructions.value && wasMarkedInstalled.value && isChromiumDesktop
)

const promptTitle = computed(() => (isIos ? "Add HRMS to Home Screen" : "Install HRMS"))

const primaryActionLabel = computed(() =>
	canInstall.value ? "Install" : showInstructions.value ? "Got it" : "How to install"
)

const promptMessage = computed(() => {
	if (canInstall.value) {
		return isAndroid
			? "Install HRMS on this phone for faster access."
			: "Install HRMS for faster access from your desktop."
	}

	if (isIos) {
		return 'Tap Share, then choose "Add to Home Screen".'
	}

	if (isSafari && isMac) {
		return 'Open the File menu, then choose "Add to Dock".'
	}

	if (isAndroid) {
		return 'Open the browser menu, then choose "Install app" or "Add to Home screen".'
	}

	return 'Open ⋮, then choose "Cast, save, and share" → "Install page as app".'
})

const installSteps = computed(() => {
	if (isIos) {
		return ['Tap the Share button in Safari.', 'Choose "Add to Home Screen".', 'Tap "Add".']
	}

	if (isSafari && isMac) {
		return ['Open the File menu.', 'Choose "Add to Dock".', 'Click "Add".']
	}

	if (isAndroid) {
		return [
			"Open the browser menu (⋮).",
			'Choose "Install app" or "Add to Home screen".',
			'Confirm by tapping "Install".',
		]
	}

	return [
		"Open the Chrome menu (⋮).",
		'Choose "Cast, save, and share".',
		'Choose "Install page as app" and confirm.',
	]
})

function scheduleOffer(delay = 2500) {
	if (!canOfferInstall()) return
	clearTimeout(showTimer)
	showTimer = window.setTimeout(() => {
		if (canOfferInstall()) showPrompt.value = true
	}, delay)
}

function handleInstallPrompt(event) {
	event.preventDefault()
	deferredPrompt.value = event
	showInstructions.value = false
	scheduleOffer(300)
}

function handleInstalled() {
	window.localStorage.removeItem(INSTALLED_KEY)
	showPrompt.value = false
	deferredPrompt.value = null
	wasMarkedInstalled.value = false
}

function dismiss() {
	dismissedThisSession.value = true
	showPrompt.value = false
	showInstructions.value = false
}

function handlePrimaryAction() {
	if (canInstall.value) {
		install()
		return
	}

	if (showInstructions.value) {
		dismiss()
		return
	}

	showInstructions.value = true
}

async function install() {
	const prompt = deferredPrompt.value
	if (!prompt) return

	showPrompt.value = false
	await prompt.prompt()
	const choice = await prompt.userChoice
	deferredPrompt.value = null

	if (choice.outcome === "accepted") {
		window.localStorage.removeItem(INSTALLED_KEY)
	} else {
		dismissedThisSession.value = true
	}
}

window.addEventListener("beforeinstallprompt", handleInstallPrompt)
window.addEventListener("appinstalled", handleInstalled)

if (canOfferInstall()) showPrompt.value = true

onMounted(() => {
	// The browser does not notify the site when an installed PWA is removed.
	// Never let a stale installation marker permanently suppress this prompt.
	window.localStorage.removeItem(INSTALLED_KEY)
	scheduleOffer()
})

onBeforeUnmount(() => {
	clearTimeout(showTimer)
	window.removeEventListener("beforeinstallprompt", handleInstallPrompt)
	window.removeEventListener("appinstalled", handleInstalled)
})
</script>

<style scoped>
@media (display-mode: standalone) {
	.pwa-install-prompt {
		display: none;
	}
}
</style>
