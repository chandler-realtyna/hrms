<template>
	<div class="flex items-center gap-4 w-full">
		<button
			type="button"
			class="relative shrink-0 rounded-full focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2"
			:aria-label="__('Change profile picture')"
			:disabled="uploading"
			@click="openFilePicker"
		>
			<img
				v-if="user.data?.user_image"
				class="h-24 w-24 rounded-full object-cover"
				:src="user.data.user_image"
				:alt="user.data?.first_name || __('Profile picture')"
			/>
			<div
				v-else
				class="flex h-24 w-24 items-center justify-center rounded-full bg-gray-200 text-2xl font-semibold uppercase text-gray-600"
			>
				{{ userInitial }}
			</div>
			<span
				class="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-gray-900 text-white"
			>
				<FeatherIcon name="camera" class="h-4 w-4" />
			</span>
		</button>

		<div class="min-w-0 flex-1">
			<p class="text-sm font-semibold text-gray-900">{{ __("Profile picture") }}</p>
			<p class="mt-1 text-xs text-gray-500">{{ __("JPG, PNG or WebP. Maximum 5 MB.") }}</p>
			<Button class="mt-3" variant="subtle" :loading="uploading" @click="openFilePicker">
				{{ __("Change photo") }}
			</Button>
		</div>

		<input
			ref="fileInput"
			type="file"
			class="hidden"
			accept="image/jpeg,image/png,image/webp"
			@change="uploadImage"
		/>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { call, FeatherIcon, toast } from "frappe-ui"

const __ = inject("$translate")
const user = inject("$user")
const employee = inject("$employee")

const fileInput = ref(null)
const uploading = ref(false)

const userInitial = computed(() => user.data?.first_name?.charAt(0) || "?")

const openFilePicker = () => {
	if (!uploading.value) fileInput.value?.click()
}

const readAsBase64 = (file) =>
	new Promise((resolve, reject) => {
		const reader = new FileReader()
		reader.onload = () => resolve(reader.result.toString().split(",")[1])
		reader.onerror = reject
		reader.readAsDataURL(file)
	})

const showUploadError = (message) => {
	toast({
		title: __("Error"),
		text: message,
		icon: "alert-circle",
		position: "bottom-center",
		iconClasses: "text-red-500",
	})
}

const uploadImage = async (event) => {
	const file = event.target.files?.[0]
	event.target.value = ""
	if (!file) return

	if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
		showUploadError(__("Choose a JPG, PNG or WebP image."))
		return
	}
	if (file.size > 5 * 1024 * 1024) {
		showUploadError(__("Profile picture must be 5 MB or smaller."))
		return
	}

	uploading.value = true
	try {
		const content = await readAsBase64(file)
		await call("hrms.api.upload_own_profile_image", {
			content,
			filename: file.name,
		})
		await user.reload()
		if (employee?.reload) await employee.reload()
		toast({
			title: __("Saved"),
			text: __("Profile picture updated"),
			icon: "check-circle",
			position: "bottom-center",
			iconClasses: "text-green-500",
		})
	} catch (error) {
		showUploadError(
			error?.messages?.[0] || error?.message || __("Failed to update profile picture")
		)
	} finally {
		uploading.value = false
	}
}
</script>
