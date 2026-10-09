"""Synthetic save-conflict/avatar browser data. Never run on production."""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import frappe
from PIL import Image

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="qa.local", sites_path=".")
frappe.connect()
assert frappe.local.site == "qa.local"
try:
	from hrms.tests.test_shared_work_state import TestSharedWorkState as Fixture
	from hrms.api import timer_state as timer, weekly_timesheet as week
	Fixture.setUpClass()
	frappe.set_user(Fixture.users[0])
	frappe.db.delete(timer.STATE, {"user": frappe.session.user})
	frappe.db.delete(timer.OPERATION, {"user": frappe.session.user})
	# Only synthetic worker weekly rows are reset for this isolated scenario.
	for name in frappe.get_all("Timesheet", filters={"employee": Fixture.employees[0]}, pluck="name"):
		for field in frappe.get_meta("Timesheet").get_table_fields():
			frappe.db.delete(field.options, {"parent": name})
		frappe.db.delete("Timesheet", {"name": name})
	now = datetime(2026, 10, 2, 9, tzinfo=timezone.utc)
	with patch.object(timer, "_now", return_value=now):
		timer.apply_action("favorite", 0, "fixture_favorite", {"project": Fixture.projects[0]})
		timer.apply_action("start", 1, "fixture_start", {"project": Fixture.projects[0]})
	with patch.object(timer, "_now", return_value=now+timedelta(minutes=10)):
		timer.apply_action("pause", 2, "fixture_pause", {})
	start = now.astimezone(timer.ZoneInfo(timer.get_system_timezone())).replace(tzinfo=None)
	data = week.get_weekly_timesheet(week_start="2026-09-27")
	left, right = (5, 10) if "--short" in sys.argv else (2, 9)
	data["time_logs"] = [dict(project=Fixture.projects[0], activity_type="Unassigned",
		from_time=start+timedelta(minutes=left), to_time=start+timedelta(minutes=right))]
	week.save_weekly_timesheet(data)
	frappe.set_user(Fixture.users[2])
	out = io.BytesIO()
	Image.new("RGB", (300, 200), "green").save(out, format="PNG")
	file = frappe.get_doc(dict(doctype="File", file_name="qa-directory-photo.png", is_private=1,
		content=out.getvalue(), attached_to_doctype="Employee", attached_to_name=Fixture.employees[1],
		attached_to_field="image")).insert(ignore_permissions=True)
	frappe.db.set_value("Employee", Fixture.employees[1], "image", file.file_url)
	if not frappe.db.exists("Employee Schedule", {"employee": Fixture.employees[1], "year": 2026}):
		schedule = frappe.get_doc(dict(doctype="Employee Schedule", employee=Fixture.employees[1], year=2026, timezone="UTC", status="Draft")).insert()
		# QA fixture only; no decision email is queued.
		frappe.db.set_value("Employee Schedule", schedule.name, "status", "Approved")
	frappe.db.commit()
	print(json.dumps({"employee": Fixture.employees[1], "original": file.file_url}))
finally:
	frappe.destroy()
