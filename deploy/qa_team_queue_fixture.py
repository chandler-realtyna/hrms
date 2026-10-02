"""Synthetic persisted queue for browser-only acceptance on the private QA site."""
import os
from datetime import timedelta
from unittest.mock import patch
import frappe

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="qa.local", sites_path=".")
frappe.connect()
try:
	assert frappe.local.site == "qa.local"
	from hrms.tests.test_team_queue_order import TestTeamQueueOrder
	TestTeamQueueOrder.setUpClass()
	fixture = TestTeamQueueOrder()
	fixture.setUp()
	try:
		fixture.seed()
		frappe.db.commit()
	finally:
		fixture.clock.stop()
	from hrms.api import timer_state as timer
	frappe.set_user(fixture.users[1])
	now = timer._now()
	with patch.object(timer, "_now", return_value=now - timedelta(minutes=10)):
		timer.apply_action("start", 0, "qa_timer_start", {"project": fixture.projects[0]})
	with patch.object(timer, "_now", return_value=now - timedelta(minutes=5)):
		timer.apply_action("switch", 1, "qa_timer_switch", {"project": fixture.projects[1]})
	frappe.db.set_value(timer.STATE, fixture.users[1], "last_error", "Automatic saving failed. Your time is preserved; please review and retry.")
	frappe.db.commit()
	print("Synthetic queue fixture: 160 current sections, 20 historical sections")
finally:
	frappe.destroy()
