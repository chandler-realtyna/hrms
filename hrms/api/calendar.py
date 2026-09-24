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
		# Frappe Time fields come back as timedelta ("9:00:00"), time, or string.
		if isinstance(time_str, _dt.timedelta):
			total_secs = int(time_str.total_seconds())
			return _dt.time(total_secs // 3600, (total_secs % 3600) // 60)
		if isinstance(time_str, _dt.time):
			return _dt.time(time_str.hour, time_str.minute)
		parts = str(time_str).split(":")
		return _dt.time(int(parts[0]), int(parts[1]))
	except Exception:
		return None


# Granularity for offered start times. Stepping by the meeting duration hides
# valid starts (e.g. a 60-min meeting at 09:30 when free 09:00-11:00), so we
# always offer quarter-hour starts and only require the duration to fit.
SLOT_STEP_MINUTES = 15
# Guardrails so a wide date range stays fast and smooth in the UI.
MAX_FINDER_DAYS = 31
MAX_FINDER_SLOTS = 200


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
	parents = frappe.db.get_all(
		"Employee Holiday",
		filters={"employee": employee, "status": "Approved"},
		pluck="name",
	)
	if not parents:
		return False
	# Query the child table directly — loading every holiday doc with get_doc
	# per employee per day is the main DB bottleneck in the finder.
	return bool(
		frappe.db.get_all(
			"Employee Holiday Date",
			filters={"parent": ["in", parents], "date": date_str},
			fields=["name"],
			limit=1,
		)
	)


def _compute_free_slots(
	working_slots: list[dict],
	busy_intervals: list[tuple[int, int]],
	duration_min: int,
	slot_tz: str = "America/New_York",
	step_min: int = SLOT_STEP_MINUTES,
) -> list[dict]:
	"""
	Given working slots (list of {start: time, end: time}) and busy_intervals
	(list of (start_minutes, end_minutes)), return a list of free {start, end}
	"HH:MM" dicts that fit duration_min minutes.

	Free windows are computed continuously first, then sliced with a
	quarter-hour step so every valid start time is offered (not just a
	duration-aligned grid).
	"""
	free = _free_windows(working_slots, busy_intervals)

	result = []
	step = max(1, min(int(step_min or SLOT_STEP_MINUTES), int(duration_min)))
	for free_start, free_end in free:
		slot_cursor = free_start
		while slot_cursor + duration_min <= free_end:
			result.append({
				"start": _time_from_minutes(slot_cursor).strftime("%H:%M"),
				"end": _time_from_minutes(slot_cursor + duration_min).strftime("%H:%M"),
			})
			slot_cursor += step
	return result


def _free_windows(
	working_slots: list[dict],
	busy_intervals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
	"""Continuous free (start_min, end_min) windows = working minus busy."""
	free: list[tuple[int, int]] = []
	for slot in working_slots:
		cursor = _minutes(slot["start"])
		end = _minutes(slot["end"])
		if end <= cursor:
			continue
		for b_start, b_end in sorted(busy_intervals):
			if b_end <= cursor or b_start >= end:
				continue
			if b_start > cursor:
				free.append((cursor, min(b_start, end)))
			cursor = max(cursor, b_end)
			if cursor >= end:
				break
		if cursor < end:
			free.append((cursor, end))
	return free


def _get_busy_times_range(
	google_calendar_name: str,
	start_utc: _dt.datetime,
	end_utc: _dt.datetime,
) -> list[dict]:
	"""Single freebusy query for a whole range (one Google call per employee)."""
	try:
		from frappe.integrations.doctype.google_calendar.google_calendar import (
			get_google_calendar_object,
		)

		google_service, account = get_google_calendar_object(google_calendar_name)
		body = {
			"timeMin": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"timeMax": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
			"items": [{"id": "primary"}],
		}
		result = google_service.freebusy().query(body=body).execute()
		return result.get("calendars", {}).get("primary", {}).get("busy", [])
	except Exception:
		return []


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
	Returns list of {date, start, end, start_utc, end_utc} dicts with UTC times.

	Fast path: one batched DB fetch per data type + one Google freebusy call
	per employee for the whole range (old code did per-employee-per-day
	Google calls + per-day get_doc loads). Correct path: intersect continuous
	UTC free windows first, then slice with a 15-min step (old code sliced
	per-employee on duration grids then intersected, which hid valid times).
	"""
	if isinstance(employees, str):
		import json
		employees = json.loads(employees)

	employees = [e for e in (employees or []) if e]
	if not employees:
		return []
	# De-dupe while keeping order
	employees = list(dict.fromkeys(employees))

	try:
		duration_minutes = int(duration_minutes)
	except Exception:
		frappe.throw(_("Invalid duration"))
	if duration_minutes < 5 or duration_minutes > 480:
		frappe.throw(_("Duration must be between 5 and 480 minutes"))

	start_date = frappe.utils.getdate(from_date)
	end_date = frappe.utils.getdate(to_date)
	if not start_date or not end_date:
		return []
	if end_date < start_date:
		start_date, end_date = end_date, start_date
	# Cap range so the UI stays fast and smooth
	total_days = (end_date - start_date).days + 1
	if total_days > MAX_FINDER_DAYS:
		end_date = start_date + _dt.timedelta(days=MAX_FINDER_DAYS - 1)

	site_tz_str = frappe.db.get_single_value("System Settings", "time_zone") or "UTC"

	# ── Batched pre-fetch (one query per data type, not per day) ──
	emp_rows = frappe.db.get_all(
		"Employee", filters={"name": ["in", employees]}, fields=["name", "user_id"]
	)
	emp_user = {r["name"]: r.get("user_id") for r in emp_rows}
	user_ids = [u for u in emp_user.values() if u]

	gcal_map: dict[str, str | None] = {emp: None for emp in employees}
	if user_ids:
		gcal_rows = frappe.db.get_all(
			"Google Calendar",
			filters={"user": ["in", user_ids]},
			fields=["name", "user", "refresh_token"],
		)
		user_gcal = {r["user"]: r["name"] for r in gcal_rows if r.get("refresh_token")}
		for emp in employees:
			uid = emp_user.get(emp)
			gcal_map[emp] = user_gcal.get(uid) if uid else None

	sched_rows = frappe.db.get_all(
		"Employee Schedule",
		filters={"employee": ["in", employees], "status": "Approved"},
		fields=["name", "employee", "timezone"],
	)
	sched_name_by_emp = {r["employee"]: r["name"] for r in sched_rows}
	sched_tz_by_emp = {r["employee"]: r.get("timezone") or site_tz_str for r in sched_rows}
	days_by_emp: dict[str, dict[int, list]] = {emp: {} for emp in employees}
	if sched_name_by_emp:
		day_rows = frappe.db.get_all(
			"Employee Schedule Day",
			filters={"parent": ["in", list(sched_name_by_emp.values())]},
			fields=["parent", "day_of_week", "day_type", "start_time", "end_time"],
		)
		parent_to_emp = {v: k for k, v in sched_name_by_emp.items()}
		for dr in day_rows:
			emp = parent_to_emp.get(dr["parent"])
			if not emp:
				continue
			try:
				dow = int(dr["day_of_week"])
			except Exception:
				continue
			if (dr.get("day_type") or "").lower() != "working":
				continue
			s_t = _parse_hhmm(dr.get("start_time"))
			e_t = _parse_hhmm(dr.get("end_time"))
			if not s_t or not e_t:
				continue
			days_by_emp[emp].setdefault(dow, []).append((s_t, e_t))

	# Leaves in range → set of date-str per employee
	leave_set: dict[str, set[str]] = {emp: set() for emp in employees}
	leave_rows = frappe.db.get_all(
		"Leave Application",
		filters={
			"employee": ["in", employees],
			"status": "Approved",
			"from_date": ["<=", str(end_date)],
			"to_date": [">=", str(start_date)],
		},
		fields=["employee", "from_date", "to_date"],
	)
	for lv in leave_rows:
		try:
			cur = frappe.utils.getdate(lv["from_date"])
			lv_end = frappe.utils.getdate(lv["to_date"])
		except Exception:
			continue
		while cur <= lv_end:
			if start_date <= cur <= end_date:
				leave_set.get(lv["employee"], set()).add(str(cur))
			cur += _dt.timedelta(days=1)

	# Personal holidays in range → set of date-str per employee
	holiday_set: dict[str, set[str]] = {emp: set() for emp in employees}
	hol_parents = frappe.db.get_all(
		"Employee Holiday",
		filters={"employee": ["in", employees], "status": "Approved"},
		fields=["name", "employee"],
	)
	if hol_parents:
		parent_to_emp_h = {r["name"]: r["employee"] for r in hol_parents}
		date_rows = frappe.db.get_all(
			"Employee Holiday Date",
			filters={
				"parent": ["in", list(parent_to_emp_h.keys())],
				"date": ["between", [str(start_date), str(end_date)]],
			},
			fields=["parent", "date"],
		)
		for dr in date_rows:
			emp = parent_to_emp_h.get(dr["parent"])
			if emp:
				try:
					holiday_set[emp].add(str(frappe.utils.getdate(dr["date"])))
				except Exception:
					holiday_set[emp].add(str(dr["date"])[:10])

	# Existing bookings for the whole range (fallback when no Google Calendar)
	bookings_by_emp: dict[str, list[tuple]] = {emp: [] for emp in employees}
	booking_rows = frappe.db.get_all(
		"Meeting Booking",
		filters=[
			["host_employee", "in", employees],
			["status", "=", "Confirmed"],
			["start_datetime", ">=", f"{start_date} 00:00:00"],
			["start_datetime", "<=", f"{end_date} 23:59:59"],
		],
		fields=["host_employee", "start_datetime", "end_datetime"],
	)
	for b in booking_rows:
		try:
			st = get_datetime(b["start_datetime"])
			en = get_datetime(b["end_datetime"])
			if st.tzinfo is None:
				st = pytz.utc.localize(st)
			if en.tzinfo is None:
				en = pytz.utc.localize(en)
			bookings_by_emp.setdefault(b["host_employee"], []).append((st, en))
		except Exception:
			continue

	# Google busy for the whole range: ONE call per employee (not per day)
	google_busy_by_emp: dict[str, list[tuple]] = {emp: [] for emp in employees}
	for emp in employees:
		gcal_name = gcal_map.get(emp)
		if not gcal_name:
			continue
		tz_str = sched_tz_by_emp.get(emp, site_tz_str)
		try:
			emp_tz = pytz.timezone(tz_str)
		except Exception:
			emp_tz = pytz.utc
		range_start_utc = emp_tz.localize(
			_dt.datetime(start_date.year, start_date.month, start_date.day, 0, 0)
		).astimezone(pytz.utc)
		range_end_utc = emp_tz.localize(
			_dt.datetime(end_date.year, end_date.month, end_date.day, 0, 0)
		).astimezone(pytz.utc) + _dt.timedelta(days=1)
		raw = _get_busy_times_range(gcal_name, range_start_utc, range_end_utc)
		intervals = []
		for b in raw:
			try:
				bs = _dt.datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
				be = _dt.datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
				intervals.append((bs, be))
			except Exception:
				continue
		google_busy_by_emp[emp] = sorted(intervals)

	now_utc = _dt.datetime.now(pytz.utc)
	step = max(1, min(SLOT_STEP_MINUTES, duration_minutes))
	results: list[dict] = []

	d = start_date
	while d <= end_date and len(results) < MAX_FINDER_SLOTS:
		per_employee_free: list[list[tuple]] = []
		valid = True
		for emp in employees:
			d_str = str(d)
			if d_str in leave_set.get(emp, set()) or d_str in holiday_set.get(emp, set()):
				valid = False
				break
			dow = d.weekday()
			tz_str = sched_tz_by_emp.get(emp, site_tz_str)
			try:
				emp_tz = pytz.timezone(tz_str)
			except Exception:
				emp_tz = pytz.utc
				tz_str = "UTC"

			day_slots = days_by_emp.get(emp, {}).get(dow)
			if day_slots is None:
				# No approved schedule → default Mon–Fri 9–17 in site tz
				if not sched_name_by_emp.get(emp):
					if dow >= 5:
						valid = False
						break
					try:
						site_tz = pytz.timezone(site_tz_str)
					except Exception:
						site_tz = pytz.utc
					emp_tz = site_tz
					day_slots = [(_dt.time(9, 0), _dt.time(17, 0))]
				else:
					valid = False
					break
			if not day_slots:
				valid = False
				break

			# Working windows as absolute UTC intervals
			working_utc: list[tuple] = []
			for s_t, e_t in day_slots:
				try:
					s_local = emp_tz.localize(_dt.datetime(d.year, d.month, d.day, s_t.hour, s_t.minute))
					e_local = emp_tz.localize(_dt.datetime(d.year, d.month, d.day, e_t.hour, e_t.minute))
					if e_local <= s_local:
						e_local += _dt.timedelta(days=1)
					working_utc.append((s_local.astimezone(pytz.utc), e_local.astimezone(pytz.utc)))
				except Exception:
					continue
			if not working_utc:
				valid = False
				break

			busy_utc = list(google_busy_by_emp.get(emp) or [])
			if not gcal_map.get(emp):
				busy_utc = list(bookings_by_emp.get(emp) or [])

			free_utc = _subtract_utc_windows(working_utc, busy_utc)
			if not free_utc:
				valid = False
				break
			per_employee_free.append(sorted(free_utc))

		if not valid or not per_employee_free:
			d += _dt.timedelta(days=1)
			continue

		# Intersect continuous free windows across everyone, then slice.
		common = per_employee_free[0]
		for other in per_employee_free[1:]:
			common = _intersect_utc_windows(common, other)
			if not common:
				break
		if common:
			for win_start, win_end in sorted(common):
				cursor = win_start
				while cursor + _dt.timedelta(minutes=duration_minutes) <= win_end:
					slot_end = cursor + _dt.timedelta(minutes=duration_minutes)
					if cursor < now_utc:
						cursor += _dt.timedelta(minutes=step)
						continue
					results.append({
						"date": str(d),
						"start_utc": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
						"end_utc": slot_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
						"start": cursor.strftime("%H:%M"),
						"end": slot_end.strftime("%H:%M"),
					})
					if len(results) >= MAX_FINDER_SLOTS:
						break
					cursor += _dt.timedelta(minutes=step)
				if len(results) >= MAX_FINDER_SLOTS:
					break

		d += _dt.timedelta(days=1)

	return results


def _subtract_utc_windows(
	working: list[tuple[_dt.datetime, _dt.datetime]],
	busy: list[tuple[_dt.datetime, _dt.datetime]],
) -> list[tuple[_dt.datetime, _dt.datetime]]:
	"""Working minus busy, all as aware UTC datetimes."""
	free: list[tuple[_dt.datetime, _dt.datetime]] = []
	for w_start, w_end in sorted(working):
		cursor = w_start
		for b_start, b_end in sorted(busy):
			if b_end <= cursor or b_start >= w_end:
				continue
			if b_start > cursor:
				free.append((cursor, min(b_start, w_end)))
			cursor = max(cursor, b_end)
			if cursor >= w_end:
				break
		if cursor < w_end:
			free.append((cursor, w_end))
	return free


def _intersect_utc_windows(
	a: list[tuple[_dt.datetime, _dt.datetime]],
	b: list[tuple[_dt.datetime, _dt.datetime]],
) -> list[tuple[_dt.datetime, _dt.datetime]]:
	"""Intersection of two sorted lists of UTC (start, end) windows."""
	out: list[tuple[_dt.datetime, _dt.datetime]] = []
	i = j = 0
	a = sorted(a)
	b = sorted(b)
	while i < len(a) and j < len(b):
		lo = max(a[i][0], b[j][0])
		hi = min(a[i][1], b[j][1])
		if lo < hi:
			out.append((lo, hi))
		if a[i][1] < b[j][1]:
			i += 1
		else:
			j += 1
	return out


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
