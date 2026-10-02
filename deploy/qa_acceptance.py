"""Run with the installed bench Python inside the isolated QA container."""
import os
import json
import sys
import unittest
from pathlib import Path

import frappe

os.chdir("/home/frappe/frappe-bench/sites")
frappe.init(site="qa.local", sites_path=".")
frappe.connect()
frappe.set_user("Administrator")
frappe.flags.in_test = True
try:
	# The application image contains compiled bundles, but the new QA sites
	# volume has no generated asset map. Link only those existing image assets.
	from frappe.build import make_asset_dirs, setup
	setup()
	make_asset_dirs()
	manifest = {}
	for app in frappe.get_installed_apps():
		public = Path(frappe.get_app_path(app, "public", "dist"))
		for kind in ("css", "js"):
			for file in (public/kind).glob("*.bundle.*."+kind):
				key = file.name.split(".bundle.")[0]+".bundle."+kind
				manifest[key] = f"/assets/{app}/dist/{kind}/{file.name}"
	Path("assets/assets.json").write_text(json.dumps(manifest))
	frappe.clear_cache()
	# A fresh app install marks migration patches applied. Materialize the
	# custom fields required by the existing Realtyna workflows on empty QA.
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({"Project": [
		dict(fieldname="custom_project_lead", label="Project Lead", fieldtype="Link", options="Employee", ignore_user_permissions=1),
		dict(fieldname="custom_project_manager", label="Project Manager", fieldtype="Link", options="Employee"),
	]}, update=True)
	from hrms.patches.v16_0 import (
		setup_weekly_timesheet_workflow,
		setup_timesheet_entry_corrections,
		create_company_director_access,
		setup_shared_work_state,
		setup_employee_invoices,
	)
	for module in (setup_weekly_timesheet_workflow, setup_timesheet_entry_corrections,
		create_company_director_access, setup_shared_work_state, setup_employee_invoices):
		if module is create_company_director_access and frappe.db.exists("Role Profile", "Company Directors"):
			continue
		module.execute()
	# Keep the fixture set narrow. The upstream full ERP test bootstrap creates
	# unrelated masters/users and includes deliberately weak test passwords.
	if not frappe.db.exists("Company", "_Test Company"):
		frappe.get_doc(dict(doctype="Company", company_name="_Test Company", abbr="_TC",
			default_currency="INR", country="India")).insert()
	frappe.db.commit()
	modules = sys.argv[1:] or ["hrms.tests.test_shared_work_state"]
	suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
	result = unittest.TextTestRunner(verbosity=2).run(suite)
	frappe.db.rollback()
	if not result.wasSuccessful(): sys.exit(1)
finally:
	frappe.destroy()
