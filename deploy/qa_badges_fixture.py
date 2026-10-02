"""Persist only synthetic review queues for browser acceptance on qa.local."""
import os
import frappe

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="qa.local", sites_path=".")
frappe.connect()
try:
	assert frappe.local.site == "qa.local"
	from hrms.tests.test_admin_desk_badges import TestAdminDeskBadges
	TestAdminDeskBadges.setUpClass()
	fixture = TestAdminDeskBadges()
	fixture.setUp()
	try:
		fixture.seed()
		frappe.db.commit()
	finally:
		fixture.clock.stop()
	print("Synthetic badges: 12 HR weeks, 64 leaves, 3 expenses, 65 holidays, 4 schedules, 5 invoices")
finally:
	frappe.destroy()
