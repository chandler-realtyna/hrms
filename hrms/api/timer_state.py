from __future__ import annotations

import copy
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import cint, get_system_timezone
from hrms.utils.account_lock import lock_current_account

STATE = "HRMS Work State"
OPERATION = "HRMS Work State Operation"


def _now():
	return datetime.now(timezone.utc)


def _iso(value):
	return value.isoformat(timespec="seconds").replace("+00:00", "Z") if value else None


def _date(value):
	try:
		date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
		if date.tzinfo is None:
			raise ValueError()
		return date.astimezone(timezone.utc)
	except (ValueError, TypeError):
		frappe.throw(_("Invalid timer timestamp."))


def _empty_timer():
	return dict(startTime=None, form=dict(project="", activity_type="", description=""),
		segments=[], isPaused=False, pausedSince=None)


@contextmanager
def _internal_write():
	old = frappe.local.flags.get("hrms_work_state_write")
	frappe.local.flags.hrms_work_state_write = True
	try:
		yield
	finally:
		frappe.local.flags.hrms_work_state_write = old


def _locked_state():
	from hrms.api.weekly_timesheet import _current_employee
	if frappe.session.user == "Guest":
		frappe.throw(_("Sign in to track time."), frappe.PermissionError)
	lock_current_account()
	if not frappe.db.get_value("User", frappe.session.user, "enabled"):
		frappe.throw(_("This account is disabled."), frappe.PermissionError)
	employee = _current_employee()
	# Lock a pre-existing per-user row before first creation, avoiding races.
	rows = frappe.db.sql("SELECT * FROM `tabHRMS Work State` WHERE name = %s FOR UPDATE", (frappe.session.user,), as_dict=True)
	if not rows:
		with _internal_write():
			doc = frappe.get_doc(dict(doctype=STATE, user=frappe.session.user, employee=employee.name,
				timer=frappe.as_json(_empty_timer()), favorites="[]", revision=0)).insert(ignore_permissions=True)
	else:
		# Locking reads see the latest committed row, not the transaction's
		# earlier repeatable-read snapshot from employee/permission lookups.
		doc = frappe.get_doc(dict(rows[0], doctype=STATE))
	if doc.employee != employee.name:
		frappe.throw(_("Your employee mapping changed. Please contact HR."), frappe.PermissionError)
	return doc


def _timer(doc):
	return copy.deepcopy(frappe.parse_json(doc.timer) or _empty_timer())


def _response(doc, saved=None):
	timer = _timer(doc)
	timer["owner"] = doc.user
	return dict(revision=cint(doc.revision), server_now=_iso(_now()), timer=timer,
		favorites=frappe.parse_json(doc.favorites) or [], initialized=bool(doc.initialized),
		last_error=doc.last_error, saved_timesheets=saved or [])


@frappe.whitelist(methods=["POST"])
def get_state():
	return _response(_locked_state())


def _project(project, open_required=True):
	if not project:
		frappe.throw(_("Select a project."))
	doc = frappe.get_doc("Project", project)
	frappe.has_permission("Project", "read", doc=doc, throw=True)
	if open_required and doc.status != "Open":
		frappe.throw(_("Project must be open."))
	return project


def _metadata(payload):
	activity = payload.get("activity_type") or ""
	if activity and not frappe.db.exists("Activity Type", activity):
		frappe.throw(_("Unknown activity type."))
	description = str(payload.get("description") or "")
	if len(description) > 10000:
		frappe.throw(_("Description is too long."))
	return dict(activity_type=activity, description=description)


def _close_active(timer, now):
	if timer["startTime"]:
		start = _date(timer["startTime"])
		if int((now-start).total_seconds()) > 0:
			timer["segments"].append(dict(id=frappe.generate_hash(length=32), **timer["form"],
				**{"from": _iso(start), "to": _iso(now)}, seconds=int((now-start).total_seconds())))
		timer["startTime"] = None


def _select_project(timer, project, payload):
	if timer["form"]["project"] != project:
		previous = next((row for row in reversed(timer["segments"]) if row["project"] == project), {})
		timer["form"] = dict(project=project, **_metadata(previous))
	else:
		timer["form"].update(_metadata(payload))


def _validate_timer(timer, now):
	if len(timer["segments"]) > 2000:
		frappe.throw(_("Save pending time before recording more intervals."))
	intervals = []
	for row in timer["segments"]:
		start, end = _date(row["from"]), _date(row["to"])
		if end <= start or end > now + timedelta(seconds=60):
			frappe.throw(_("Invalid timer interval."))
		row["seconds"] = int((end-start).total_seconds())
		intervals.append((start, end))
	if timer["startTime"]:
		start = _date(timer["startTime"])
		if start > now + timedelta(seconds=60):
			frappe.throw(_("Invalid timer start."))
		intervals.append((start, now))
	intervals.sort()
	if any(current[0] < previous[1] for previous, current in zip(intervals, intervals[1:])):
		frappe.throw(_("Timer intervals cannot overlap."))


def _save_project(doc, timer, project):
	from hrms.api.weekly_timesheet import save_weekly_timer_log
	names = []
	target_zone = ZoneInfo(get_system_timezone())
	for row in timer["segments"]:
		if project and row["project"] != project:
			continue
		name = save_weekly_timer_log(employee=doc.employee, project=row["project"],
			from_time=_date(row["from"]).astimezone(target_zone).replace(tzinfo=None),
			to_time=_date(row["to"]).astimezone(target_zone).replace(tzinfo=None),
			activity_type=row.get("activity_type"), description=row.get("description"))
		if name not in names:
			names.append(name)
	# The caller and all interval saves share a transaction: failures preserve all.
	timer["segments"] = [row for row in timer["segments"] if project and row["project"] != project]
	return names


def _adjust(timer, seconds, now):
	seconds = max(-86400, min(86400, cint(seconds)))
	project = timer["form"]["project"]
	if seconds > 0:
		row = None if timer["startTime"] else next((row for row in reversed(timer["segments"]) if row["project"] == project), None)
		if not timer["startTime"] and row is None:
			frappe.throw(_("Nothing to adjust yet."))
		start = _date(timer["startTime"] or row["from"])
		bounds = [_date(other["to"]) for other in timer["segments"] if other is not row and _date(other["to"]) <= start]
		seconds = min(seconds, int((start-max(bounds)).total_seconds())) if bounds else seconds
		if timer["startTime"]:
			timer["startTime"] = _iso(start-timedelta(seconds=seconds))
		else:
			row["from"] = _iso(start-timedelta(seconds=seconds))
	else:
		remaining = -seconds
		if timer["startTime"]:
			start = _date(timer["startTime"])
			take = min(remaining, max(0, int((now-start).total_seconds())))
			timer["startTime"] = _iso(start+timedelta(seconds=take))
			remaining -= take
		for row in reversed(timer["segments"]):
			if row["project"] != project or not remaining:
				continue
			take = min(remaining, int((_date(row["to"])-_date(row["from"])).total_seconds()))
			row["to"] = _iso(_date(row["to"])-timedelta(seconds=take))
			remaining -= take
		timer["segments"] = [row for row in timer["segments"] if _date(row["to"]) > _date(row["from"])]


def _import_legacy(doc, payload, now):
	if doc.initialized:
		frappe.throw(_("A synchronized timer already exists. Your local draft was kept."))
	legacy = payload.get("timer") or {}
	if legacy.get("owner") not in {doc.user, doc.employee}:
		frappe.throw(_("The local timer belongs to a different account."), frappe.PermissionError)
	timer = _empty_timer()
	timer["form"] = dict(project=legacy.get("form", {}).get("project") or "", **_metadata(legacy.get("form", {})))
	if timer["form"]["project"]:
		_project(timer["form"]["project"])
	timer["startTime"] = legacy.get("startTime")
	if timer["startTime"] and not timer["form"]["project"]:
		frappe.throw(_("The local timer has no project. Your draft was kept for recovery."))
	timer["isPaused"] = bool(legacy.get("isPaused")) and not timer["startTime"]
	timer["pausedSince"] = legacy.get("pausedSince") if timer["isPaused"] else None
	for row in legacy.get("segments") or []:
		timer["segments"].append(dict(id=frappe.generate_hash(length=32), project=_project(row.get("project")),
			**_metadata(row), **{"from": row.get("from"), "to": row.get("to")}))
	if timer["isPaused"] and not timer["pausedSince"]:
		timer["pausedSince"] = _iso(now)
	if timer["pausedSince"]:
		_date(timer["pausedSince"])
	_validate_timer(timer, now)
	return timer


@frappe.whitelist(methods=["POST"])
def apply_action(action, expected_revision, operation_id, payload=None):
	payload = frappe.parse_json(payload) or {}
	if not isinstance(payload, dict) or not re.fullmatch(r"\d+", str(expected_revision)):
		frappe.throw(_("Invalid timer request."))
	if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", str(operation_id)):
		frappe.throw(_("Invalid timer operation."))
	doc = _locked_state()
	fingerprint = hashlib.sha256(json.dumps([action, cint(expected_revision), payload], sort_keys=True).encode()).hexdigest()
	key = hashlib.sha256(f"{doc.user}|{operation_id}".encode()).hexdigest()
	receipts = frappe.db.sql("SELECT * FROM `tabHRMS Work State Operation` WHERE name = %s FOR UPDATE", (key,), as_dict=True)
	if receipts:
		previous = frappe.get_doc(dict(receipts[0], doctype=OPERATION))
		if previous.fingerprint != fingerprint:
			frappe.throw(_("An operation identifier cannot be reused for different actions."))
		return _response(doc, (frappe.parse_json(previous.result) or {}).get("saved_timesheets"))
	if cint(expected_revision) != cint(doc.revision):
		frappe.local.response.http_status_code = 409
		frappe.throw(_("The timer changed on another device. Please retry from the latest state."), frappe.TimestampMismatchError)
	timer, now = _timer(doc), _now()
	favorites = frappe.parse_json(doc.favorites) or []
	saved = []
	project = payload.get("project") or timer["form"]["project"]
	if action in {"start", "resume", "switch"}:
		_project(project)
		if timer["startTime"]:
			timer["form"].update(_metadata(payload))
		_close_active(timer, now)
		_select_project(timer, project, payload)
		timer.update(startTime=_iso(now), isPaused=False, pausedSince=None)
	elif action == "pause":
		timer["form"].update(_metadata(payload))
		_close_active(timer, now)
		timer.update(isPaused=bool(timer["segments"]), pausedSince=_iso(now))
	elif action == "metadata":
		if project != timer["form"]["project"]:
			frappe.throw(_("The active project changed."))
		timer["form"].update(_metadata(payload))
	elif action in {"save", "discard"}:
		if not project:
			frappe.throw(_("Select the project to save or discard."))
		if timer["form"]["project"] == project:
			timer["form"].update(_metadata(payload))
			_close_active(timer, now)
		if action == "save":
			saved = _save_project(doc, timer, project)
		else:
			timer["segments"] = [row for row in timer["segments"] if row["project"] != project]
		if not timer["startTime"]:
			timer["isPaused"] = bool(timer["segments"])
			timer["pausedSince"] = _iso(now) if timer["segments"] else None
			if not timer["segments"]:
				timer["form"] = _empty_timer()["form"]
			elif not any(row["project"] == timer["form"]["project"] for row in timer["segments"]):
				last = timer["segments"][-1]
				timer["form"] = dict(project=last["project"], **_metadata(last))
	elif action == "adjust":
		_adjust(timer, payload.get("seconds"), now)
	elif action == "favorite":
		_project(project, open_required=False)
		favorites = [name for name in favorites if name != project] if project in favorites else [project, *favorites]
	elif action in {"import", "import_favorites"}:
		if action == "import":
			timer = _import_legacy(doc, payload, now)
		for item in payload.get("favorites") or []:
			name = item.get("name") if isinstance(item, dict) else item
			_project(name, open_required=False)
			if name not in favorites:
				favorites.append(name)
	elif action == "autosave":
		if not timer["isPaused"] or not timer["pausedSince"] or now-_date(timer["pausedSince"]) < timedelta(hours=2):
			frappe.throw(_("The paused timer is not due for automatic saving."))
		saved = _save_project(doc, timer, None)
		timer = _empty_timer()
	elif action == "retry_save":
		# Retry completed intervals only; recording on another project continues.
		saved = _save_project(doc, timer, None)
		if not timer["startTime"]:
			timer = _empty_timer()
	else:
		frappe.throw(_("Unknown timer action."))
	_validate_timer(timer, now)
	doc.timer, doc.favorites = frappe.as_json(timer), frappe.as_json(favorites)
	doc.revision = cint(doc.revision)+1
	doc.initialized, doc.last_error = 1, None
	doc.paused_due = (_date(timer["pausedSince"])+timedelta(hours=2)).replace(tzinfo=None) if timer["isPaused"] and timer["pausedSince"] else None
	with _internal_write():
		doc.save(ignore_permissions=True)
		frappe.get_doc(dict(doctype=OPERATION, name=key, user=doc.user,
			fingerprint=fingerprint, result=frappe.as_json(dict(saved_timesheets=saved)))).insert(ignore_permissions=True)
	frappe.publish_realtime("hrms:timer_changed", {"revision": doc.revision}, user=doc.user, after_commit=True)
	return _response(doc, saved)


def reject_legacy_save(user):
	if frappe.local.flags.get("hrms_work_state_write"):
		return
	lock_current_account()
	if frappe.db.sql("SELECT name FROM `tabHRMS Work State` WHERE user=%s AND initialized=1 FOR UPDATE", (user,)):
		frappe.throw(_("Use the synchronized timer to save time. Your local draft was kept."))


def save_paused_timers():
	old_user = frappe.session.user
	try:
		for row in frappe.get_all(STATE, filters={"paused_due": ("<=", _now().replace(tzinfo=None))}, fields=["user", "revision"]):
			try:
				frappe.set_user(row.user)
				current = _locked_state()
				if cint(current.revision) != cint(row.revision):
					frappe.db.rollback()
					continue
				timer = _timer(current)
				due = (_date(timer["pausedSince"]) + timedelta(hours=2)) if timer["isPaused"] and timer["pausedSince"] else None
				if not due or due > _now():
					# A stale scheduling marker is not a failed interval save.
					frappe.db.set_value(STATE, current.name, "paused_due", due.replace(tzinfo=None) if due else None, update_modified=False)
					frappe.db.commit()
					continue
				apply_action("autosave", row.revision, f"autosave_{row.revision}", {})
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title="Paused timer autosave failed")
				frappe.db.set_value(STATE, {"name": row.user, "revision": row.revision}, {
					"last_error": _("Automatic saving failed. Your time is preserved; please review and retry."),
					"paused_due": (_now()+timedelta(minutes=30)).replace(tzinfo=None),
				})
				frappe.db.commit()
	finally:
		frappe.set_user(old_user)


def notify_running_timers():
	from hrms.api import notify_long_running_timer
	old_user = frappe.session.user
	try:
		for row in frappe.get_all(STATE, filters={"initialized": 1}, fields=["user", "timer", "notified_start"]):
			timer = frappe.parse_json(row.timer) or {}
			start = timer.get("startTime")
			if not start or start == row.notified_start or _now()-_date(start) < timedelta(hours=2):
				continue
			try:
				frappe.set_user(row.user)
				notify_long_running_timer(_locked_state().employee, timer["form"]["project"], start)
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title="Shared timer reminder failed")
	finally:
		frappe.set_user(old_user)
