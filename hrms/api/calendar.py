"""
Google Calendar integration + public booking + meeting finder.

Relies on Frappe's built-in Google Calendar DocType for OAuth token storage
and the Google Calendar API client. Employees must connect via the Frappe
desk (Framework → Integrations → Google Calendar) before scheduling features
are enabled.
"""

from __future__ import annotations

import datetime as _dt

import frappe
import pytz
from frappe import _
from frappe.utils import get_datetime


# ── Helpers ───────────────────────────────────────────────────────────────────


def _current_employee() -> str:
	current_user = frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": current_user, "status": "Active"}, "name")
	if not employee:
		frappe.throw(_("No active employee record found for this user"), frappe.PermissionError)
	return employee


def _get_google_calendar_for_user(user: str) -> str | None:
	"""Return the name of the user's Google Calendar doc if it has a refresh_token."""
	return frappe.db.get_value(
		"Google Calendar",
		{"user": user, "refresh_token": ("is", "set")},
		"name",
	)


def _get_busy_times(
	google_calendar_name: str,
	start_dt: _dt.datetime,
	end_dt: _dt.datetime,
) -> list[dict]:
	"""Return list of {start, end} ISO strings from Google freebusy API."""
	try:
		from frappe.integrations.doctype.google_calendar.google_calendar import (
			get_google_calendar_object,
		)

		google_service, account = get_google_calendar_object(google_calendar_name)
		# Always query primary calendar — that's where real user events live
		body = {
			"timeMin": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"timeMax": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"items": [{"id": "primary"}],
		}
		result = google_service.freebusy().query(body=body).execute()
		return result.get("calendars", {}).get("primary", {}).get("busy", [])
	except Exception:
		return []


def _parse_hhmm(time_str) -> _dt.time | None:
	if not time_str:
		return None
	try:
		parts = str(time_str).split(":")
		return _dt.time(int(parts[0]), int(parts[1]))
	except Exception:
		return None


def _minutes(t: _dt.time) -> int:
	return t.hour * 60 + t.minute


def _time_from_minutes(m: int) -> _dt.time:
	return _dt.time(m // 60, m % 60)


def _get_employee_schedule_for_date(employee: str, date: _dt.date) -> list[dict]:
	"""
	Return list of working slots [{start: time, end: time}] for the employee on the given date.
	Falls back to 9 AM–5 PM Mon–Fri if no approved Employee Schedule exists.
	"""
	schedule = frappe.db.get_value(
		"Employee Schedule",
		{"employee": employee, "status": "Approved"},
		["name", "timezone"],
		as_dict=True,
	)

	site_tz = frappe.db.get_single_value("System Settings", "time_zone") or "UTC"

	if not schedule:
		# Default working hours: Mon–Fri 9 AM – 5 PM in the site timezone
		dow = date.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
		if dow >= 5:
			return []
		return [{"start": _dt.time(9, 0), "end": _dt.time(17, 0), "timezone": site_tz}]

	doc = frappe.get_doc("Employee Schedule", schedule["name"], ignore_permissions=True)
	dow = date.weekday()  # 0=Monday
	slots = []
	for day in doc.schedule_days:
		if int(day.day_of_week) == dow and (day.day_type or "").lower() == "working":
			start_t = _parse_hhmm(day.start_time)
			end_t = _parse_hhmm(day.end_time)
			if start_t and end_t:
				slots.append({"start": start_t, "end": end_t, "timezone": schedule["timezone"] or site_tz})
	return slots


def _is_on_leave(employee: str, date: _dt.date) -> bool:
	date_str = str(date)
	return bool(
		frappe.db.exists(
			"Leave Application",
			{
				"employee": employee,
				"status": "Approved",
				"from_date": ("<=", date_str),
				"to_date": (">=", date_str),
			},
		)
	)


def _is_personal_holiday(employee: str, date: _dt.date) -> bool:
	date_str = str(date)
	holiday_records = frappe.db.get_all(
		"Employee Holiday",
		filters={"employee": employee, "status": "Approved"},
		fields=["name"],
		limit=50,
	)
	for rec in holiday_records:
		hol_doc = frappe.get_doc("Employee Holiday", rec["name"])
		for h in hol_doc.holidays:
			if str(h.date)[:10] == date_str:
				return True
	return False


def _compute_free_slots(
	working_slots: list[dict],
	busy_intervals: list[tuple[int, int]],
	duration_min: int,
	slot_tz: str = "America/New_York",
) -> list[dict]:
	"""
	Given working slots (list of {start: time, end: time}) and busy_intervals
	(list of (start_minutes, end_minutes)), return a list of free {start, end}
	"HH:MM" dicts that fit duration_min minutes.
	"""
	free = []
	for slot in working_slots:
		cursor = _minutes(slot["start"])
		end = _minutes(slot["end"])
		# Sort busy intervals and walk through them
		sorted_busy = sorted(busy_intervals)
		for b_start, b_end in sorted_busy:
			if b_end <= cursor or b_start >= end:
				continue
			# Free time before this busy block
			if b_start > cursor and b_start - cursor >= duration_min:
				free.append((cursor, b_start))
			cursor = max(cursor, b_end)
		# Remaining free time after all busy blocks
		if end - cursor >= duration_min:
			free.append((cursor, end))

	result = []
	for free_start, free_end in free:
		slot_cursor = free_start
		while slot_cursor + duration_min <= free_end:
			result.append({
				"start": _time_from_minutes(slot_cursor).strftime("%H:%M"),
				"end": _time_from_minutes(slot_cursor + duration_min).strftime("%H:%M"),
			})
			slot_cursor += duration_min
	return result


def _get_existing_bookings_for_date(employee: str, date: _dt.date) -> list[tuple[int, int]]:
	"""Return list of (start_minutes, end_minutes) for confirmed bookings on this date."""
	date_str = str(date)
	bookings = frappe.db.get_all(
		"Meeting Booking",
		filters=[
			["host_employee", "=", employee],
			["status", "=", "Confirmed"],
			["start_datetime", ">=", f"{date_str} 00:00:00"],
			["start_datetime", "<=", f"{date_str} 23:59:59"],
		],
		fields=["start_datetime", "end_datetime"],
	)
	intervals = []
	for b in bookings:
		st = get_datetime(b["start_datetime"])
		en = get_datetime(b["end_datetime"])
		intervals.append((_minutes(st.time()), _minutes(en.time())))
	return intervals


def _google_busy_as_intervals(
	gcal_name: str | None,
	date: _dt.date,
	emp_tz_str: str,
) -> list[tuple[int, int]]:
	"""Return busy intervals in local employee timezone as (start_min, end_min) pairs."""
	if not gcal_name:
		return []
	try:
		emp_tz = pytz.timezone(emp_tz_str)
	except Exception:
		emp_tz = pytz.utc

	day_start_utc = emp_tz.localize(
		_dt.datetime(date.year, date.month, date.day, 0, 0)
	).astimezone(pytz.utc)
	day_end_utc = day_start_utc + _dt.timedelta(days=1)

	raw_busy = _get_busy_times(gcal_name, day_start_utc, day_end_utc)
	intervals = []
	for b in raw_busy:
		try:
			b_start = _dt.datetime.fromisoformat(b["start"].replace("Z", "+00:00")).astimezone(emp_tz)
			b_end = _dt.datetime.fromisoformat(b["end"].replace("Z", "+00:00")).astimezone(emp_tz)
			intervals.append((_minutes(b_start.time()), _minutes(b_end.time())))
		except Exception:
			pass
	return intervals


# ── Connection status ─────────────────────────────────────────────────────────


@frappe.whitelist()
def get_calendar_connection_status() -> dict:
	"""Return Google Calendar connection status for the current user."""
	current_user = frappe.session.user
	gcal_name = _get_google_calendar_for_user(current_user)

	result: dict = {
		"is_connected": bool(gcal_name),
		"google_calendar_name": gcal_name,
		"booking_slug": None,
		"booking_enabled": False,
	}

	employee = frappe.db.get_value("Employee", {"user_id": current_user, "status": "Active"}, "name")
	if employee:
		settings = frappe.db.get_value(
			"Employee Booking Settings",
			{"employee": employee},
			["booking_slug", "booking_enabled"],
			as_dict=True,
		)
		if settings:
			result["booking_slug"] = settings["booking_slug"]
			result["booking_enabled"] = bool(settings["booking_enabled"])

	return result


# ── Booking settings ──────────────────────────────────────────────────────────


@frappe.whitelist()
def get_booking_settings() -> dict:
	"""Return booking settings for the current employee."""
	employee = _current_employee()
	settings = frappe.db.get_value(
		"Employee Booking Settings",
		{"employee": employee},
		["name", "booking_slug", "booking_enabled", "min_notice_hours", "slot_duration_options"],
		as_dict=True,
	)
	if not settings:
		return {
			"booking_slug": None,
			"booking_enabled": False,
			"min_notice_hours": 1,
			"slot_duration_options": "30,60",
		}
	return settings


@frappe.whitelist()
def save_booking_settings(
	booking_slug: str,
	booking_enabled: int,
	min_notice_hours: int = 1,
	slot_duration_options: str = "30,60",
) -> dict:
	"""Create or update booking settings for the current employee."""
	employee = _current_employee()
	existing_name = frappe.db.get_value("Employee Booking Settings", {"employee": employee}, "name")

	if existing_name:
		doc = frappe.get_doc("Employee Booking Settings", existing_name)
	else:
		doc = frappe.new_doc("Employee Booking Settings")
		doc.employee = employee

	doc.booking_slug = booking_slug.strip().lower()
	doc.booking_enabled = int(booking_enabled)
	doc.min_notice_hours = int(min_notice_hours)
	doc.slot_duration_options = slot_duration_options
	doc.save()

	return {
		"booking_slug": doc.booking_slug,
		"booking_enabled": bool(doc.booking_enabled),
		"min_notice_hours": doc.min_notice_hours,
		"slot_duration_options": doc.slot_duration_options,
	}


# ── Public booking (guest-accessible) ────────────────────────────────────────


@frappe.whitelist(allow_guest=True)
def get_booking_page_info(slug: str) -> dict:
	"""Return public employee info for the booking page."""
	settings = frappe.db.get_value(
		"Employee Booking Settings",
		{"booking_slug": slug, "booking_enabled": 1},
		["employee", "slot_duration_options", "min_notice_hours"],
		as_dict=True,
	)
	if not settings:
		frappe.throw(_("Booking page not found"), frappe.DoesNotExistError)

	employee_data = frappe.db.get_value(
		"Employee",
		settings["employee"],
		["employee_name", "designation", "image"],
		as_dict=True,
	)

	durations = [int(d.strip()) for d in (settings["slot_duration_options"] or "30,60").split(",") if d.strip().isdigit()]

	return {
		"employee": settings["employee"],
		"employee_name": employee_data["employee_name"],
		"designation": employee_data["designation"] or "",
		"image": employee_data["image"] or "",
		"duration_options": durations,
		"min_notice_hours": settings["min_notice_hours"] or 1,
	}


@frappe.whitelist(allow_guest=True)
def get_available_slots(slug: str, date: str, duration_minutes: int) -> list[dict]:
	"""
	Return available booking slots for an employee on a given date.
	Respects: working hours, leaves, personal holidays, existing bookings, Google Calendar busy times.
	"""
	duration_minutes = int(duration_minutes)

	settings = frappe.db.get_value(
		"Employee Booking Settings",
		{"booking_slug": slug, "booking_enabled": 1},
		["employee", "min_notice_hours"],
		as_dict=True,
	)
	if not settings:
		return []

	employee = settings["employee"]
	date_obj = frappe.utils.getdate(date)
	min_notice_hours = int(settings["min_notice_hours"] or 1)

	# Check if employee is off that day
	if _is_on_leave(employee, date_obj) or _is_personal_holiday(employee, date_obj):
		return []

	working_slots = _get_employee_schedule_for_date(employee, date_obj)
	if not working_slots:
		return []

	emp_tz_str = working_slots[0].get("timezone", "America/New_York")

	# Collect all busy intervals
	busy: list[tuple[int, int]] = []

	host_user = frappe.db.get_value("Employee", employee, "user_id")
	gcal_name = _get_google_calendar_for_user(host_user) if host_user else None

	if gcal_name:
		# Google Calendar freebusy is real-time: cancelled events are automatically
		# freed, so we use it as the sole source of truth when connected.
		busy.extend(_google_busy_as_intervals(gcal_name, date_obj, emp_tz_str))
	else:
		# No Google Calendar → fall back to Meeting Booking records so at least
		# confirmed bookings block the slot (even though cancellations won't sync).
		busy.extend(_get_existing_bookings_for_date(employee, date_obj))

	# Filter past / too-soon slots by comparing slot UTC datetimes to the UTC
	# cutoff. This avoids any naive timezone comparison: slot times are in
	# emp_tz, we localise them, convert to UTC, then compare.
	emp_tz_obj = pytz.timezone(emp_tz_str)
	now_utc = _dt.datetime.now(pytz.utc)
	cutoff_utc = now_utc + _dt.timedelta(hours=min_notice_hours)

	def _slot_start_utc(hhmm_minutes: int) -> _dt.datetime:
		naive = _dt.datetime(date_obj.year, date_obj.month, date_obj.day) + _dt.timedelta(minutes=hhmm_minutes)
		return emp_tz_obj.localize(naive).astimezone(pytz.utc)

	slots = _compute_free_slots(working_slots, busy, duration_minutes)
	slots = [s for s in slots if _slot_start_utc(_parse_hhmm_str_to_minutes(s["start"])) >= cutoff_utc]

	return {"slots": slots, "timezone": emp_tz_str}


def _parse_hhmm_str_to_minutes(hhmm: str) -> int:
	h, m = hhmm.split(":")
	return int(h) * 60 + int(m)


@frappe.whitelist(allow_guest=True)
def create_booking(
	slug: str,
	start: str,
	end: str,
	booker_name: str,
	booker_email: str,
	title: str,
	description: str = "",
	timezone: str = "",
) -> dict:
	"""Create a confirmed meeting booking and a Google Calendar event with Meet link."""
	settings = frappe.db.get_value(
		"Employee Booking Settings",
		{"booking_slug": slug, "booking_enabled": 1},
		["employee"],
		as_dict=True,
	)
	if not settings:
		frappe.throw(_("Booking page not found"), frappe.DoesNotExistError)

	start_dt = get_datetime(start)
	end_dt = get_datetime(end)

	booking = frappe.new_doc("Meeting Booking")
	booking.host_employee = settings["employee"]
	booking.booker_name = booker_name.strip()
	booking.booker_email = booker_email.strip().lower()
	booking.start_datetime = start_dt
	booking.end_datetime = end_dt
	booking.title = title.strip()
	booking.description = description.strip()
	booking.status = "Confirmed"
	booking.insert(ignore_permissions=True)
	frappe.db.commit()  # commit immediately so slot is blocked for concurrent requests

	# Create Google Calendar event with Meet link and booker as guest
	meet_link = None
	try:
		host_user = frappe.db.get_value("Employee", settings["employee"], "user_id")
		gcal_name = _get_google_calendar_for_user(host_user) if host_user else None

		if gcal_name:
			from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
			google_service, _ = get_google_calendar_object(gcal_name)

			# Use the timezone the booking page already showed the user (passed from
			# the frontend). If not provided, fall back to the employee's schedule tz.
			if not timezone:
				_ws = _get_employee_schedule_for_date(settings["employee"], start_dt.date())
				timezone = (
					_ws[0].get("timezone")
					if _ws
					else frappe.db.get_single_value("System Settings", "time_zone") or "UTC"
				)

			event_body = {
				"summary": title.strip(),
				"description": description.strip() or "",
				"start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
				"end":   {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
				# Only add booker as guest — host is the organizer automatically
				"attendees": [
					{
						"email": booker_email.strip().lower(),
						"displayName": booker_name.strip(),
					}
				],
				"conferenceData": {
					"createRequest": {
						"requestId": f"hrms-{booking.name}",
						"conferenceSolutionKey": {"type": "hangoutsMeet"},
					}
				},
				"reminders": {"useDefault": True},
			}

			# Always insert into primary calendar — attendee invitations work reliably there
			created = google_service.events().insert(
				calendarId="primary",
				body=event_body,
				conferenceDataVersion=1,
				sendUpdates="all",
			).execute()

			for ep in created.get("conferenceData", {}).get("entryPoints", []):
				if ep.get("entryPointType") == "video":
					meet_link = ep.get("uri")
					break
	except Exception as e:
		frappe.log_error(str(e), "Booking: Google Calendar event creation failed")

	return {
		"booking_id": booking.name,
		"start": str(booking.start_datetime),
		"end": str(booking.end_datetime),
		"title": booking.title,
		"meet_link": meet_link,
	}


# ── Meeting finder (authenticated) ────────────────────────────────────────────


@frappe.whitelist()
def find_meeting_slots(
	employees: list | str,
	duration_minutes: int | str,
	from_date: str,
	to_date: str,
) -> list[dict]:
	"""
	Find overlapping free windows across all specified employees.
	Returns list of {date, start, end} dicts (times in each employee's local timezone
	converted to a common UTC reference for comparison).
	"""
	if isinstance(employees, str):
		import json
		employees = json.loads(employees)

	duration_minutes = int(duration_minutes)
	start_date = frappe.utils.getdate(from_date)
	end_date = frappe.utils.getdate(to_date)

	# Pre-fetch Google Calendar names for each employee
	gcal_map: dict[str, str | None] = {}
	for emp in employees:
		user_id = frappe.db.get_value("Employee", emp, "user_id")
		gcal_map[emp] = _get_google_calendar_for_user(user_id) if user_id else None

	now_utc = _dt.datetime.now(pytz.utc)
	results = []
	d = start_date
	while d <= end_date:
		# Build free-window list per employee (in minutes-of-day, UTC-normalized)
		per_employee_free: list[list[tuple[int, int]]] = []
		valid = True

		for emp in employees:
			if _is_on_leave(emp, d) or _is_personal_holiday(emp, d):
				valid = False
				break

			working_slots = _get_employee_schedule_for_date(emp, d)
			if not working_slots:
				valid = False
				break

			emp_tz_str = working_slots[0].get("timezone", "America/New_York")
			try:
				emp_tz = pytz.timezone(emp_tz_str)
			except Exception:
				emp_tz = pytz.utc

			# Convert working slots to UTC minutes for intersection
			busy: list[tuple[int, int]] = []
			if gcal_map[emp]:
				# Google Calendar freebusy is real-time — cancelled events are freed
				# automatically, so it's the authoritative source when connected.
				busy.extend(_google_busy_as_intervals(gcal_map[emp], d, emp_tz_str))
			else:
				busy.extend(_get_existing_bookings_for_date(emp, d))

			free_slots = _compute_free_slots(working_slots, busy, duration_minutes)

			# Convert HH:MM strings to UTC minute-of-day for intersection
			utc_free: list[tuple[int, int]] = []
			for fs in free_slots:
				try:
					start_local = emp_tz.localize(
						_dt.datetime(d.year, d.month, d.day,
						*[int(x) for x in fs["start"].split(":")])
					)
					end_local = emp_tz.localize(
						_dt.datetime(d.year, d.month, d.day,
						*[int(x) for x in fs["end"].split(":")])
					)
					s_utc = start_local.astimezone(pytz.utc)
					e_utc = end_local.astimezone(pytz.utc)
					utc_free.append((_dt_to_minutes(s_utc), _dt_to_minutes(e_utc)))
				except Exception:
					pass

			per_employee_free.append(utc_free)

		if not valid or not per_employee_free:
			d += _dt.timedelta(days=1)
			continue

		# Intersect all employees' free windows
		intersection = per_employee_free[0]
		for other in per_employee_free[1:]:
			intersection = _intersect_intervals(intersection, other)

		# Build slots from intersected windows, skipping ones already past
		for (win_start, win_end) in intersection:
			cursor = win_start
			while cursor + duration_minutes <= win_end:
				slot_start_utc = _dt.datetime(d.year, d.month, d.day, tzinfo=pytz.utc) + _dt.timedelta(minutes=cursor)
				if slot_start_utc < now_utc:
					cursor += duration_minutes
					continue
				slot_end_utc = slot_start_utc + _dt.timedelta(minutes=duration_minutes)
				results.append({
					"date": str(d),
					"start_utc": slot_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
					"end_utc": slot_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
					"start": slot_start_utc.strftime("%H:%M"),
					"end": slot_end_utc.strftime("%H:%M"),
				})
				cursor += duration_minutes

		d += _dt.timedelta(days=1)

	return results


def _dt_to_minutes(dt: _dt.datetime) -> int:
	return dt.hour * 60 + dt.minute


def _intersect_intervals(
	a: list[tuple[int, int]],
	b: list[tuple[int, int]],
) -> list[tuple[int, int]]:
	"""Return the intersection of two sorted lists of (start, end) intervals."""
	result = []
	i = j = 0
	while i < len(a) and j < len(b):
		lo = max(a[i][0], b[j][0])
		hi = min(a[i][1], b[j][1])
		if lo < hi:
			result.append((lo, hi))
		if a[i][1] < b[j][1]:
			i += 1
		else:
			j += 1
	return result


@frappe.whitelist()
def send_meeting_invitation(
	employees: list | str,
	start: str,
	end: str,
	title: str,
	description: str = "",
) -> dict:
	"""
	Create a Google Calendar event with Meet link for all participants.
	Does NOT use Frappe Event sync to avoid duplicate calendar entries.
	"""
	import uuid as _uuid

	if isinstance(employees, str):
		import json
		employees = json.loads(employees)

	organizer_user = frappe.session.user
	organizer_gcal = _get_google_calendar_for_user(organizer_user)

	start_dt = get_datetime(start)
	end_dt = get_datetime(end)

	# find_meeting_slots returns slot times in UTC (start/end fields are %H:%M
	# formatted from UTC datetimes). Declare UTC so Google Calendar places the
	# event at the correct moment without any offset shift.
	org_tz_str = "UTC"

	# Collect participant emails (excluding organizer — they are added automatically)
	attendees = []
	for emp in employees:
		user_id = frappe.db.get_value("Employee", emp, "user_id")
		if not user_id or user_id == organizer_user:
			continue
		email = frappe.db.get_value("User", user_id, "email")
		name  = frappe.db.get_value("User", user_id, "full_name")
		if email:
			attendees.append({"email": email, "displayName": name or email})

	event_link = None
	meet_link  = None

	if organizer_gcal:
		try:
			from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
			google_service, _ = get_google_calendar_object(organizer_gcal)

			event_body = {
				"summary": title,
				"description": description or "",
				"start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": org_tz_str},
				"end":   {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": org_tz_str},
				"attendees": attendees,
				"conferenceData": {
					"createRequest": {
						"requestId": str(_uuid.uuid4()),
						"conferenceSolutionKey": {"type": "hangoutsMeet"},
					}
				},
			}

			created = google_service.events().insert(
				calendarId="primary",
				body=event_body,
				conferenceDataVersion=1,
				sendUpdates="all",
			).execute()

			event_link = created.get("htmlLink")
			for ep in created.get("conferenceData", {}).get("entryPoints", []):
				if ep.get("entryPointType") == "video":
					meet_link = ep.get("uri")
					break
		except Exception as e:
			frappe.log_error(str(e), "send_meeting_invitation: Google Calendar failed")

	return {"event_link": event_link, "meet_link": meet_link}


# ── Google Calendar connect helper ────────────────────────────────────────────


@frappe.whitelist()
def get_google_calendar_authorize_url() -> dict:
	"""
	Return the OAuth2 authorization URL for connecting Google Calendar.
	Creates a Google Calendar doc for the current user if one doesn't exist.
	"""
	from frappe.integrations.doctype.google_calendar.google_calendar import authorize_access

	current_user = frappe.session.user

	# Find or create a Google Calendar doc for this user
	gcal_name = frappe.db.get_value("Google Calendar", {"user": current_user}, "name")
	if not gcal_name:
		gcal = frappe.new_doc("Google Calendar")
		gcal.user = current_user
		gcal.calendar_name = f"{frappe.db.get_value('User', current_user, 'full_name')} Calendar"
		gcal.google_calendar_id = "primary"
		# Disable Frappe's background sync — we create Google Calendar events directly
		# via the API so we don't get duplicates from the scheduler
		gcal.pull_from_google_calendar = 0
		gcal.push_to_google_calendar = 0
		gcal.insert(ignore_permissions=True)
		gcal_name = gcal.name
	else:
		# Disable sync on existing doc too
		frappe.db.set_value("Google Calendar", gcal_name, {
			"pull_from_google_calendar": 0,
			"push_to_google_calendar": 0,
		})

	# Kick off the OAuth flow — returns {"url": "https://accounts.google.com/..."}
	result = authorize_access(gcal_name, reauthorize=True)
	return {"auth_url": result.get("url"), "google_calendar": gcal_name}
