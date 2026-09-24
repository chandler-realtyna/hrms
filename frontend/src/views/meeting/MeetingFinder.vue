<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start"><ion-back-button default-href="/home" /></ion-buttons>
				<ion-title>{{ __("Meeting Finder") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<MeetingFinderPanel />
		</ion-content>
	</ion-page>
</template>

<script setup>
import { inject } from "vue"
import { IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons, IonBackButton } from "@ionic/vue"

import MeetingFinderPanel from "./MeetingFinderPanel.vue"

const __ = inject("$translate")
</script>
