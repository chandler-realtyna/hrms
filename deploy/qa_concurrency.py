"""Independent database connections and actual Redis events on isolated QA only."""
import json
import multiprocessing
import os
import uuid
import traceback

import frappe
from redis import Redis

USER = "worker@qa.invalid"


def connect():
	os.chdir("/home/frappe/frappe-bench/sites")
	frappe.init(site="qa.local", sites_path=".")
	frappe.connect()
	frappe.set_user(USER)


def device(barrier, results, revision, operation, project):
	connect()
	try:
		from hrms.api.timer_state import apply_action
		frappe.db.get_value("User", USER, "enabled")
		barrier.wait(timeout=15)
		state = apply_action("start", revision, operation, {"project": project})
		frappe.db.commit()
		results.put(("ok", state["revision"]))
	except frappe.TimestampMismatchError:
		frappe.db.rollback()
		results.put(("stale", None))
	except Exception as error:
		frappe.db.rollback()
		traceback.print_exc()
		results.put((type(error).__name__, str(error)))
	finally:
		frappe.destroy()


def race(revision, operations, project):
	context = multiprocessing.get_context("spawn")
	barrier, results = context.Barrier(2), context.Queue()
	processes = [context.Process(target=device, args=(barrier, results, revision, operation, project)) for operation in operations]
	for process in processes:
		process.start()
	output = [results.get(timeout=30) for _ in processes]
	for process in processes:
		process.join(timeout=10)
		assert not process.is_alive(), "QA request did not finish"
		assert process.exitcode == 0
	return output


def week_device(barrier, results, payload, label):
	connect()
	try:
		from hrms.api.weekly_timesheet import save_weekly_timesheet
		frappe.db.get_value("User", USER, "enabled")
		barrier.wait(timeout=15)
		payload["note"] = label
		saved = save_weekly_timesheet(payload, expected_modified=payload["modified"])
		frappe.db.commit()
		results.put(("ok", saved["modified"]))
	except frappe.TimestampMismatchError:
		frappe.db.rollback()
		results.put(("stale", None))
	except Exception as error:
		frappe.db.rollback()
		traceback.print_exc()
		results.put((type(error).__name__, str(error)))
	finally:
		frappe.destroy()


if __name__ == "__main__":
	connect()
	from hrms.api import timer_state as timer
	project = frappe.db.get_value("Project", {"project_name": "QA Alpha"})
	assert project and frappe.local.site == "qa.local"
	before = timer.get_state()
	frappe.db.commit()
	revision = before["revision"]
	frappe.destroy()
	unique = uuid.uuid4().hex
	output = race(revision, ["race_a_"+unique, "race_b_"+unique], project)
	assert sorted(kind for kind, _ in output) == ["ok", "stale"], output
	print("PASS concurrent devices: one commit, one stale rejection")
	output = race(revision+1, ["replay_"+unique]*2, project)
	assert output == [("ok", revision+2)]*2, output
	print("PASS simultaneous identical requests: one revision and ledger receipt")
	connect()
	pubsub = Redis.from_url(frappe.conf.redis_queue).pubsub()
	pubsub.subscribe("events")
	pubsub.get_message(timeout=2)
	state = timer.get_state()
	timer.apply_action("favorite", state["revision"], "notify_"+unique, {"project": project})
	assert pubsub.get_message(timeout=0.5) is None, "Notification escaped before commit"
	frappe.db.commit()
	payload = None
	for _ in range(10):
		event = pubsub.get_message(timeout=1)
		if event:
			candidate = json.loads(event["data"])
			if candidate["event"] == "hrms:timer_changed":
				payload = candidate
				break
	assert payload, "Committed timer notification was not delivered to Redis"
	assert payload["room"] == "user:"+USER, payload
	print("PASS actual Redis notification: after commit and private user room")
	pubsub.close()
	frappe.destroy()
	connect()
	from hrms.api.weekly_timesheet import get_weekly_timesheet
	week = get_weekly_timesheet()
	frappe.db.commit()
	frappe.destroy()
	if week.get("name"):
		context = multiprocessing.get_context("spawn")
		barrier, results = context.Barrier(2), context.Queue()
		processes = [context.Process(target=week_device, args=(barrier, results, week, "Concurrent QA "+str(i))) for i in range(2)]
		for process in processes: process.start()
		output = [results.get(timeout=30) for _ in processes]
		for process in processes:
			process.join(timeout=10)
			assert not process.is_alive() and process.exitcode == 0
		assert sorted(kind for kind, _ in output) == ["ok", "stale"], output
		print("PASS simultaneous weekly saves: one commit, one explicit version conflict")
