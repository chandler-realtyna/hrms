<template>
	<ion-page>
		<ion-content :scroll-y="true">
			<div class="booking-root">

				<!-- Loading -->
				<div v-if="pageInfo.loading" class="booking-page" style="display:flex;align-items:center;justify-content:center">
					<div style="text-align:center">
						<div class="spin" style="border-color:#bfdbfe;border-top-color:#2563eb;width:40px;height:40px;margin:0 auto 1rem"></div>
						<p style="font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#94a3b8">Loading</p>
					</div>
				</div>

				<!-- Not found -->
				<div v-else-if="notFound" class="booking-page" style="display:flex;align-items:center;justify-content:center;padding:2rem">
					<div class="booking-card" style="padding:3rem 2rem;max-width:360px;text-align:center">
						<div style="width:64px;height:64px;background:#fee2e2;border-radius:1rem;display:flex;align-items:center;justify-content:center;margin:0 auto 1.5rem">
							<svg style="width:32px;height:32px;color:#f87171" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
								<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
							</svg>
						</div>
						<h2 style="font-size:1.125rem;font-weight:600;color:#0f172a;margin-bottom:.5rem">Page Not Found</h2>
						<p style="font-size:.875rem;color:#64748b;line-height:1.6">This booking link is invalid or has been disabled.</p>
					</div>
				</div>

				<!-- Main -->
				<div v-else-if="pageInfo.data" class="booking-page">
					<div class="booking-max">

						<!-- Employee header -->
						<div class="booking-card" style="padding:1.25rem 1.5rem;margin-bottom:.75rem">
							<div style="display:flex;align-items:center;gap:1rem">
								<div style="width:52px;height:52px;border-radius:.875rem;background:#eff6ff;border:2px solid #bfdbfe;display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0">
									<img v-if="pageInfo.data.image" :src="pageInfo.data.image" style="width:100%;height:100%;object-fit:cover"/>
									<span v-else class="display-font" style="font-size:1.25rem;font-weight:700;color:#2563eb">{{ pageInfo.data.employee_name?.charAt(0) }}</span>
								</div>
								<div style="flex:1;min-width:0">
									<h1 class="display-font" style="font-size:1.0625rem;font-weight:600;color:#0f172a">{{ pageInfo.data.employee_name }}</h1>
									<p v-if="pageInfo.data.designation" style="font-size:.8125rem;color:#94a3b8;margin-top:.125rem">{{ pageInfo.data.designation }}</p>
								</div>
								<div style="display:flex;flex-wrap:wrap;gap:.375rem;justify-content:flex-end">
									<span v-if="selectedDuration" class="chip chip-green">
										<svg style="width:10px;height:10px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
										{{ selectedDuration }} min
									</span>
									<span v-if="selectedDate" class="chip chip-green">
										<svg style="width:10px;height:10px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
										{{ selectedDate }}
									</span>
									<span v-if="selectedSlot" class="chip chip-green">
										<svg style="width:10px;height:10px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
										{{ selectedSlot.start }}
									</span>
								</div>
							</div>
						</div>

						<!-- Stepper -->
						<div class="booking-card" style="padding:1rem 1.5rem;margin-bottom:.75rem">
							<div style="display:flex;align-items:center">
								<template v-for="(label, i) in stepLabels" :key="i">
									<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0">
										<div :style="stepCircleStyle(i+1)">
											<svg v-if="stepStatus(i+1)==='done'" style="width:14px;height:14px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
											<span v-else style="font-size:.6875rem;font-weight:700">{{ i+1 }}</span>
										</div>
										<span :style="stepLabelStyle(i+1)">{{ label }}</span>
									</div>
									<div v-if="i < stepLabels.length-1" :style="stepLineStyle(i+1)"></div>
								</template>
							</div>
						</div>

						<!-- SUCCESS -->
						<div v-if="confirmed" class="booking-card" style="padding:2.5rem 2rem;text-align:center">
							<div style="width:64px;height:64px;background:#dcfce7;border-radius:1rem;display:flex;align-items:center;justify-content:center;margin:0 auto 1.5rem">
								<svg style="width:32px;height:32px;color:#22c55e" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
								</svg>
							</div>
							<h2 class="display-font" style="font-size:1.5rem;font-weight:600;color:#0f172a;margin-bottom:.5rem">You're all set!</h2>
							<p style="font-size:.875rem;color:#64748b;margin-bottom:1.75rem">Confirmation sent to <strong style="color:#334155">{{ bookerEmail }}</strong></p>
							<div style="background:#f8fafc;border-radius:1rem;border:1px solid #e2e8f0;overflow:hidden;margin-bottom:1.25rem">
								<div class="summary-row"><span class="summary-label">Meeting</span><span class="summary-value">{{ confirmedTitle }}</span></div>
								<div class="summary-row" style="border-top:1px solid #f1f5f9"><span class="summary-label">Date &amp; time</span><span class="summary-value">{{ formattedConfirmedDate }}</span></div>
								<div class="summary-row" style="border-top:1px solid #f1f5f9"><span class="summary-label">Duration</span><span class="summary-value">{{ selectedDuration }} min</span></div>
							</div>
							<a v-if="confirmedMeetLink" :href="confirmedMeetLink" target="_blank" class="meet-btn">
								<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 8.5v7L20 19V5l-4.5 3.5zM4 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V8z"/></svg>
								Join with Google Meet
							</a>
							<p v-if="confirmedMeetLink" style="font-size:.75rem;color:#94a3b8;margin-bottom:1rem">A calendar invite was sent to {{ bookerEmail }}</p>
							<button @click="resetForm" class="link-btn" style="margin-top:.5rem">Book another time</button>
						</div>

						<!-- Split layout -->
						<div v-else class="split-layout">

							<!-- ══ LEFT: Calendar ══ -->
							<div class="booking-card calendar-card">
								<!-- Month navigation -->
								<div class="cal-header">
									<button @click="prevMonth" :disabled="!canGoBack" class="cal-nav-btn" :style="!canGoBack ? 'opacity:.3;cursor:default' : ''">
										<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
									</button>
									<span class="cal-month-title">{{ monthNames[calendarMonth] }} {{ calendarYear }}</span>
									<button @click="nextMonth" class="cal-nav-btn">
										<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
									</button>
								</div>

								<!-- Day-of-week labels -->
								<div class="cal-grid">
									<div v-for="l in dayLabels" :key="l" class="cal-label">{{ l }}</div>

									<!-- Calendar days -->
									<button
										v-for="(day, idx) in calendarDays"
										:key="idx"
										:disabled="isDateDisabled(day)"
										@click="selectCalendarDay(day)"
										:class="['cal-day', {
											'cal-day--empty': !day,
											'cal-day--disabled': day && isDateDisabled(day),
											'cal-day--selected': day && isDateSelected(day),
											'cal-day--today': day && isToday(day) && !isDateSelected(day),
											'cal-day--available': day && !isDateDisabled(day) && !isDateSelected(day),
										}]"
									>
										<span v-if="day" class="cal-day-num">{{ day }}</span>
										<span v-if="day && isToday(day)" class="cal-today-dot"></span>
									</button>
								</div>

								<!-- Legend -->
								<div class="cal-legend">
									<span class="legend-item"><span class="legend-dot" style="background:#2563eb"></span> Selected</span>
									<span class="legend-item"><span class="legend-dot" style="background:#e2e8f0"></span> Unavailable</span>
								</div>
							</div>

							<!-- ══ RIGHT: Form ══ -->
							<div class="right-panel">

								<!-- Duration -->
								<div class="booking-card" style="padding:1.25rem 1.5rem;margin-bottom:.75rem">
									<div class="section-header">
										<div class="section-icon" :style="currentStep>1?'background:#dcfce7':'background:#eff6ff'">
											<svg v-if="currentStep>1" style="width:18px;height:18px;color:#22c55e" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
											<svg v-else style="width:18px;height:18px;color:#2563eb" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
										</div>
										<div>
											<h3 class="section-title">Meeting Duration</h3>
											<p class="section-desc">How long do you need?</p>
										</div>
									</div>
									<div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1rem">
										<button
											v-for="d in pageInfo.data.duration_options"
											:key="d"
											@click="selectDuration(d)"
											class="dur-btn"
											:style="selectedDuration===d ? 'background:#1e293b;color:#fff;border-color:#1e293b;box-shadow:0 4px 12px rgba(30,41,59,.2)' : ''"
										>
											<span class="dur-num">{{ d }}</span>
											<span class="dur-unit">min</span>
										</button>
									</div>
								</div>

								<!-- Prompt to pick date -->
								<transition name="step-in">
									<div v-if="selectedDuration && !selectedDate" class="pick-date-hint">
										<svg style="width:20px;height:20px;color:#93c5fd;flex-shrink:0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
											<path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
										</svg>
										<span>Now pick a date from the calendar</span>
									</div>
								</transition>

								<!-- Time slots -->
								<transition name="step-in">
									<div v-if="selectedDate && selectedDuration" class="booking-card" style="padding:1.25rem 1.5rem;margin-bottom:.75rem">
										<div class="section-header" style="margin-bottom:1rem">
											<div class="section-icon" :style="currentStep>3?'background:#dcfce7':'background:#f0f9ff'">
												<svg v-if="currentStep>3" style="width:18px;height:18px;color:#22c55e" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
												<svg v-else style="width:18px;height:18px;color:#0284c7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
											</div>
											<div>
												<h3 class="section-title">Available Times</h3>
												<p class="section-desc">{{ selectedDate }}<span v-if="formattedTimezone"> · {{ formattedTimezone }}</span></p>
											</div>
										</div>

										<div v-if="slotsLoading" style="display:flex;align-items:center;gap:.75rem;padding:.25rem 0">
											<div class="spin" style="border-color:#bfdbfe;border-top-color:#2563eb;width:18px;height:18px;flex-shrink:0"></div>
											<span style="font-size:.875rem;color:#94a3b8">Checking availability…</span>
										</div>
										<div v-else-if="slots.length===0" style="text-align:center;padding:1.5rem 0">
											<p style="font-size:.875rem;font-weight:500;color:#475569;margin-bottom:.25rem">No slots available</p>
											<p style="font-size:.8125rem;color:#94a3b8">Try another date</p>
										</div>
										<div v-else class="slot-grid">
											<button
												v-for="slot in slots"
												:key="slot.start"
												@click="selectedSlot = slot"
												class="slot-btn"
												:style="selectedSlot?.start===slot.start ? 'background:#2563eb;color:#fff;border-color:#2563eb;box-shadow:0 4px 12px rgba(37,99,235,.25)' : ''"
											>{{ slot.start }}</button>
										</div>
									</div>
								</transition>

								<!-- Details form -->
								<transition name="step-in">
									<div v-if="selectedSlot" class="booking-card" style="padding:1.25rem 1.5rem">
										<div class="section-header" style="margin-bottom:1rem">
											<div class="section-icon" style="background:#fffbeb">
												<svg style="width:18px;height:18px;color:#d97706" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
											</div>
											<div>
												<h3 class="section-title">Your Details</h3>
												<p class="section-desc">{{ selectedDate }} · {{ selectedSlot.start }}–{{ selectedSlot.end }} · {{ selectedDuration }}min</p>
											</div>
										</div>

										<!-- Booking summary -->
										<div style="background:linear-gradient(135deg,#eff6ff,#f5f3ff);border:1px solid #dbeafe;border-radius:.875rem;padding:.875rem 1rem;margin-bottom:1.25rem">
											<div style="display:grid;grid-template-columns:1fr 1fr;gap:.625rem">
												<div class="sum-item">
													<span class="sum-label">Date</span>
													<span class="sum-val">{{ selectedDate }}</span>
												</div>
												<div class="sum-item">
													<span class="sum-label">Time</span>
													<span class="sum-val">{{ selectedSlot.start }} – {{ selectedSlot.end }}</span>
												</div>
												<div class="sum-item">
													<span class="sum-label">With</span>
													<span class="sum-val">{{ pageInfo.data.employee_name }}</span>
												</div>
												<div class="sum-item">
													<span class="sum-label">Duration</span>
													<span class="sum-val">{{ selectedDuration }} minutes</span>
												</div>
											</div>
										</div>

										<div style="display:flex;flex-direction:column;gap:.875rem">
											<div>
												<label class="field-label">Your Name</label>
												<div class="field-wrap">
													<svg class="field-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
													<input v-model="bookerName" type="text" placeholder="Full name" class="field-input"/>
												</div>
											</div>
											<div>
												<label class="field-label">Email</label>
												<div class="field-wrap">
													<svg class="field-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
													<input v-model="bookerEmail" type="email" placeholder="your@email.com" class="field-input"/>
												</div>
											</div>
											<div>
												<label class="field-label">Meeting Title</label>
												<div class="field-wrap">
													<svg class="field-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"/></svg>
													<input v-model="meetingTitle" type="text" placeholder="e.g. Introduction call" class="field-input"/>
												</div>
											</div>
											<div>
												<label class="field-label">Notes <span style="font-weight:400;color:#cbd5e1">(optional)</span></label>
												<textarea v-model="meetingDescription" rows="2" placeholder="Anything to share in advance…" class="field-input" style="resize:none;padding:.75rem 1rem"></textarea>
											</div>
											<div v-if="bookingError" style="display:flex;gap:.5rem;background:#fef2f2;border:1px solid #fecaca;border-radius:.75rem;padding:.75rem 1rem">
												<svg style="width:16px;height:16px;color:#f87171;flex-shrink:0;margin-top:2px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
												<p style="font-size:.875rem;color:#ef4444">{{ bookingError }}</p>
											</div>
											<button
												@click="submitBooking"
												:disabled="!canSubmit||submitting"
												class="submit-btn"
												:style="canSubmit&&!submitting ? 'background:#2563eb;color:#fff;cursor:pointer;box-shadow:0 8px 20px rgba(37,99,235,.2)' : 'background:#f1f5f9;color:#cbd5e1;cursor:not-allowed'"
											>
												<span v-if="submitting" style="display:flex;align-items:center;justify-content:center;gap:.5rem">
													<div class="spin" style="border-color:rgba(255,255,255,.3);border-top-color:#fff;width:16px;height:16px"></div>
													Confirming…
												</span>
												<span v-else>Confirm Booking →</span>
											</button>
										</div>
									</div>
								</transition>

							</div><!-- /right-panel -->
						</div><!-- /split-layout -->

						<div style="height:2rem"></div>
					</div>
				</div>

			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, computed, onMounted } from "vue"
import { useRoute } from "vue-router"
import { IonPage, IonContent } from "@ionic/vue"

const route = useRoute()
const slug = route.params.slug
const __ = (str) => str

// ── Page data ──────────────────────────────────────
const notFound = ref(false)
const pageInfo = ref({ loading: true, data: null })

async function loadPageInfo() {
	try {
		const res = await fetch(`/api/method/hrms.api.calendar.get_booking_page_info?slug=${encodeURIComponent(slug)}`)
		const json = await res.json()
		if (json.exc || !json.message) { notFound.value = true }
		else { pageInfo.value = { loading: false, data: json.message } }
	} catch { notFound.value = true }
	finally { pageInfo.value.loading = false }
}

// ── Booking state ──────────────────────────────────
const selectedDuration  = ref(null)
const selectedDate      = ref("")
const selectedSlot      = ref(null)
const bookerName        = ref("")
const bookerEmail       = ref("")
const meetingTitle      = ref("")
const meetingDescription = ref("")
const slots             = ref([])
const slotsTimezone     = ref("")
const slotsLoading      = ref(false)

const formattedTimezone = computed(() => {
	const tz = slotsTimezone.value
	if (!tz) return ""
	try {
		const parts = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "long" })
			.formatToParts(new Date())
		const longName = parts.find(p => p.type === "timeZoneName")?.value || tz
		const offset = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "shortOffset" })
			.formatToParts(new Date()).find(p => p.type === "timeZoneName")?.value || ""
		return offset ? `${longName} (${offset})` : longName
	} catch {
		return tz
	}
})
const submitting        = ref(false)
const bookingError      = ref("")
const confirmed         = ref(false)
const confirmedTitle    = ref("")
const confirmedStart    = ref("")
const confirmedMeetLink = ref("")

onMounted(loadPageInfo)

const minDate = computed(() => {
	const d = new Date(); d.setDate(d.getDate() + 1)
	return d.toISOString().split("T")[0]
})

const canSubmit = computed(() =>
	bookerName.value.trim() && bookerEmail.value.includes("@") && meetingTitle.value.trim()
)

const formattedConfirmedDate = computed(() => {
	if (!confirmedStart.value) return ""
	return new Date(confirmedStart.value).toLocaleString()
})

// ── Stepper ────────────────────────────────────────
const currentStep = computed(() => {
	if (!selectedDuration.value) return 1
	if (!selectedDate.value)     return 2
	if (!selectedSlot.value)     return 3
	return 4
})

const stepStatus = (n) => n < currentStep.value ? "done" : n === currentStep.value ? "active" : "pending"
const stepLabels = ["Duration", "Date", "Time", "Details"]

const stepCircleStyle = (n) => {
	const s = stepStatus(n)
	const base = "width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .3s;"
	if (s==="done")   return base+"background:#22c55e;color:#fff;"
	if (s==="active") return base+"background:#2563eb;color:#fff;box-shadow:0 0 0 4px #dbeafe;"
	return base+"background:#f1f5f9;color:#94a3b8;"
}

const stepLabelStyle = (n) => {
	const s = stepStatus(n)
	const c = s==="active" ? "#2563eb" : s==="done" ? "#22c55e" : "#94a3b8"
	return `font-size:.625rem;font-weight:600;margin-top:.375rem;color:${c};text-transform:uppercase;letter-spacing:.04em;`
}

const stepLineStyle = (n) => {
	const done = stepStatus(n)==="done"
	return `flex:1;height:2px;margin:.75rem .375rem;border-radius:9999px;background:${done?"#86efac":"#f1f5f9"};transition:background .4s;`
}

// ── Calendar ───────────────────────────────────────
const calendarDate  = ref(new Date())
const monthNames    = ["January","February","March","April","May","June","July","August","September","October","November","December"]
const dayLabels     = ["Mo","Tu","We","Th","Fr","Sa","Su"]

const calendarYear  = computed(() => calendarDate.value.getFullYear())
const calendarMonth = computed(() => calendarDate.value.getMonth())

const calendarDays = computed(() => {
	const year = calendarYear.value, month = calendarMonth.value
	const firstDay = new Date(year, month, 1)
	const lastDay  = new Date(year, month + 1, 0)
	let offset = firstDay.getDay(); offset = offset === 0 ? 6 : offset - 1
	const days = []
	for (let i = 0; i < offset; i++) days.push(null)
	for (let d = 1; d <= lastDay.getDate(); d++) days.push(d)
	return days
})

const canGoBack = computed(() => {
	const now = new Date()
	return calendarYear.value > now.getFullYear() ||
		(calendarYear.value === now.getFullYear() && calendarMonth.value > now.getMonth())
})

function isDateDisabled(day) {
	if (!day) return true
	const date = new Date(calendarYear.value, calendarMonth.value, day)
	const today = new Date(); today.setHours(0,0,0,0)
	if (date < today) return true
	const dow = date.getDay()
	return dow === 0 || dow === 6
}

function isDateSelected(day) {
	if (!day) return false
	const y = calendarYear.value
	const m = String(calendarMonth.value+1).padStart(2,"0")
	const d = String(day).padStart(2,"0")
	return selectedDate.value === `${y}-${m}-${d}`
}

function isToday(day) {
	if (!day) return false
	const t = new Date()
	return day===t.getDate() && calendarMonth.value===t.getMonth() && calendarYear.value===t.getFullYear()
}

function prevMonth() {
	if (!canGoBack.value) return
	const d = new Date(calendarDate.value); d.setMonth(d.getMonth()-1); calendarDate.value = d
}

function nextMonth() {
	const d = new Date(calendarDate.value); d.setMonth(d.getMonth()+1); calendarDate.value = d
}

function selectCalendarDay(day) {
	if (isDateDisabled(day)) return
	const y = calendarYear.value
	const m = String(calendarMonth.value+1).padStart(2,"0")
	const d = String(day).padStart(2,"0")
	const dateStr = `${y}-${m}-${d}`
	if (selectedDate.value === dateStr) return
	selectedDate.value = dateStr
	selectedSlot.value = null
	slots.value = []
	if (selectedDuration.value) loadSlots()
}

// ── API helpers ────────────────────────────────────
function selectDuration(d) {
	selectedDuration.value = d; selectedSlot.value = null; slots.value = []
	if (selectedDate.value) loadSlots()
}

async function callApi(method, args={}) {
	const params = new URLSearchParams({ cmd: method, ...args })
	const res = await fetch("/api/method/"+method, {
		method:"POST",
		headers:{ "Content-Type":"application/x-www-form-urlencoded","X-Frappe-CSRF-Token":"fetch" },
		body: params,
	})
	const json = await res.json()
	if (json.exc) throw new Error(json._error_message||"Request failed")
	return json.message
}

async function loadSlots() {
	if (!selectedDate.value||!selectedDuration.value) return
	selectedSlot.value = null; slotsLoading.value = true; slots.value = []
	try {
		const res = await callApi("hrms.api.calendar.get_available_slots",{ slug, date:selectedDate.value, duration_minutes:selectedDuration.value })
		slots.value = res?.slots || []
		slotsTimezone.value = res?.timezone || ""
	} catch { slots.value = [] }
	finally { slotsLoading.value = false }
}

async function submitBooking() {
	if (!canSubmit.value) return
	submitting.value = true; bookingError.value = ""
	try {
		const startStr = `${selectedDate.value} ${selectedSlot.value.start}:00`
		const endStr   = `${selectedDate.value} ${selectedSlot.value.end}:00`
		const result = await callApi("hrms.api.calendar.create_booking",{
			slug, start:startStr, end:endStr,
			booker_name:bookerName.value.trim(), booker_email:bookerEmail.value.trim().toLowerCase(),
			title:meetingTitle.value.trim(), description:meetingDescription.value.trim(),
			timezone: slotsTimezone.value,
		})
		confirmedTitle.value   = meetingTitle.value
		confirmedStart.value   = startStr
		confirmedMeetLink.value = result?.meet_link||""
		confirmed.value = true
	} catch(e) {
		bookingError.value = e?.message||"Failed to create booking. Please try again."
	} finally { submitting.value = false }
}

function resetForm() {
	selectedDuration.value=null; selectedDate.value=""; selectedSlot.value=null
	bookerName.value=""; bookerEmail.value=""; meetingTitle.value=""; meetingDescription.value=""
	slots.value=[]; slotsTimezone.value=""; confirmed.value=false; bookingError.value=""; confirmedMeetLink.value=""
}
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap');

.booking-root { font-family:'DM Sans',system-ui,sans-serif; }
.booking-root .display-font { font-family:'DM Serif Display',Georgia,serif; }

/* Page shell */
.booking-page { min-height:100%; background:#f1f5f9; padding:1.25rem 1rem; }
.booking-max  { max-width:900px; margin:0 auto; }

/* Cards */
.booking-card { background:#fff; border-radius:1.125rem; box-shadow:0 1px 3px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.04); }

/* Split layout */
.split-layout { display:flex; gap:.75rem; align-items:flex-start; }
.calendar-card { flex:0 0 auto; width:300px; padding:1.25rem; }
.right-panel   { flex:1; min-width:0; display:flex; flex-direction:column; gap:.75rem; }

@media(max-width:660px) {
	.split-layout { flex-direction:column; }
	.calendar-card { width:100%; }
}

/* Calendar header */
.cal-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:1rem; }
.cal-month-title { font-size:.9375rem; font-weight:600; color:#0f172a; }
.cal-nav-btn { width:30px; height:30px; border-radius:.5rem; background:#f8fafc; border:1px solid #e2e8f0; display:flex; align-items:center; justify-content:center; cursor:pointer; color:#64748b; transition:all .15s; }
.cal-nav-btn:hover:not(:disabled) { background:#f1f5f9; color:#1e293b; }

/* Calendar grid */
.cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:2px; }
.cal-label { font-size:.625rem; font-weight:600; color:#94a3b8; text-align:center; text-transform:uppercase; padding:.375rem 0; letter-spacing:.04em; }

/* Calendar days */
.cal-day { position:relative; border:none; background:transparent; border-radius:.5rem; padding:0; cursor:pointer; display:flex; flex-direction:column; align-items:center; justify-content:center; aspect-ratio:1; transition:all .12s ease; font-family:'DM Sans',sans-serif; }
.cal-day-num { font-size:.8125rem; font-weight:500; line-height:1; }
.cal-today-dot { position:absolute; bottom:3px; left:50%; transform:translateX(-50%); width:4px; height:4px; border-radius:50%; background:#2563eb; }

.cal-day--empty   { pointer-events:none; }
.cal-day--disabled{ cursor:not-allowed; }
.cal-day--disabled .cal-day-num { color:#d1d5db; }

.cal-day--available .cal-day-num { color:#1e293b; }
.cal-day--available:hover { background:#eff6ff; }
.cal-day--available:hover .cal-day-num { color:#2563eb; }

.cal-day--today .cal-day-num { color:#2563eb; font-weight:700; }

.cal-day--selected { background:#2563eb; border-radius:.625rem; }
.cal-day--selected .cal-day-num { color:#fff; font-weight:700; }

/* Calendar legend */
.cal-legend { display:flex; gap:1rem; margin-top:.875rem; padding-top:.75rem; border-top:1px solid #f1f5f9; }
.legend-item { display:flex; align-items:center; gap:.375rem; font-size:.6875rem; color:#94a3b8; }
.legend-dot { width:8px; height:8px; border-radius:50%; }

/* Section headers */
.section-header { display:flex; align-items:flex-start; gap:.875rem; }
.section-icon { width:38px; height:38px; border-radius:.75rem; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.section-title { font-size:.9375rem; font-weight:600; color:#0f172a; }
.section-desc  { font-size:.8125rem; color:#94a3b8; margin-top:.125rem; }

/* Duration buttons */
.dur-btn { display:flex; flex-direction:column; align-items:center; padding:.625rem 1.125rem; border-radius:.875rem; border:2px solid #e2e8f0; background:#f8fafc; color:#475569; cursor:pointer; transition:all .15s; font-family:'DM Sans',sans-serif; }
.dur-btn:hover { border-color:#94a3b8; background:#fff; }
.dur-num { font-size:1.125rem; font-weight:700; line-height:1; }
.dur-unit { font-size:.625rem; opacity:.6; margin-top:.125rem; }

/* Date prompt */
.pick-date-hint { display:flex; align-items:center; gap:.625rem; background:#eff6ff; border:1px dashed #bfdbfe; border-radius:.875rem; padding:.875rem 1rem; font-size:.875rem; color:#2563eb; font-weight:500; }

/* Slots */
.slot-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:.4rem; }
@media(min-width:400px){ .slot-grid { grid-template-columns:repeat(4,1fr); } }
.slot-btn { padding:.6rem .25rem; border-radius:.75rem; border:2px solid #e2e8f0; background:#f8fafc; color:#475569; font-size:.8125rem; font-weight:500; cursor:pointer; transition:all .12s; font-family:'DM Sans',sans-serif; }
.slot-btn:hover { border-color:#93c5fd; background:#eff6ff; color:#1d4ed8; }

/* Form */
.field-label { display:block; font-size:.6875rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.07em; margin-bottom:.4rem; }
.field-wrap  { position:relative; display:flex; align-items:center; }
.field-icon  { width:15px; height:15px; color:#94a3b8; position:absolute; left:.875rem; flex-shrink:0; }
.field-input { width:100%; background:#f8fafc; border:2px solid #e2e8f0; border-radius:.75rem; padding:.75rem .875rem .75rem 2.5rem; font-size:.875rem; color:#1e293b; font-family:'DM Sans',sans-serif; outline:none; transition:border-color .15s,background .15s; }
.field-input::placeholder { color:#cbd5e1; }
.field-input:focus { border-color:#93c5fd; background:#fff; }

/* Summary */
.sum-item  { display:flex; flex-direction:column; }
.sum-label { font-size:.625rem; color:#93c5fd; font-weight:600; text-transform:uppercase; letter-spacing:.06em; }
.sum-val   { font-size:.8125rem; font-weight:600; color:#1e40af; margin-top:.125rem; }

/* Submit */
.submit-btn { width:100%; padding:.875rem; border-radius:.875rem; border:none; font-size:.9375rem; font-weight:600; font-family:'DM Sans',sans-serif; transition:all .2s; }
.submit-btn:hover:not(:disabled) { transform:translateY(-1px); }

/* Chips */
.chip { display:inline-flex; align-items:center; gap:.25rem; font-size:.6875rem; font-weight:500; padding:.25rem .5rem; border-radius:9999px; }
.chip-green { background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0; }

/* Summary rows */
.summary-row { display:flex; align-items:center; justify-content:space-between; padding:.75rem 1.25rem; }
.summary-label { font-size:.875rem; color:#94a3b8; }
.summary-value { font-size:.875rem; font-weight:500; color:#334155; text-align:right; margin-left:1rem; }

/* Meet button */
.meet-btn { display:inline-flex; align-items:center; justify-content:center; gap:.5rem; background:#1a73e8; color:#fff; border-radius:.875rem; padding:.875rem 1.5rem; text-decoration:none; font-size:.9375rem; font-weight:600; margin-bottom:.75rem; transition:background .15s; width:100%; }
.meet-btn:hover { background:#1557b0; }

/* Link button */
.link-btn { background:none; border:none; cursor:pointer; font-family:'DM Sans',sans-serif; font-size:.875rem; color:#94a3b8; text-decoration:underline; text-underline-offset:3px; }
.link-btn:hover { color:#475569; }

/* Spinner */
.spin { border-radius:50%; border:2px solid; animation:spin .7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

/* Step transition */
.step-in-enter-active { transition:opacity .35s ease,transform .35s cubic-bezier(.16,1,.3,1); }
.step-in-enter-from   { opacity:0; transform:translateY(16px); }
</style>
