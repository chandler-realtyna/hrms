"""
Post-migrate hooks for HRMS customisations.
Each function is called by Frappe after every `bench migrate`.
"""

import json

import frappe


def add_scheduling_to_hr_setup_workspace():
	"""
	Ensure Employee Schedule and Employee Holiday appear in the HR Setup
	workspace — both in the main-content card area AND in the left sidebar.

	We patch the live database record rather than relying on JSON file
	sync, which silently skips files whose modified timestamp is older
	than the record already in the database.
	"""
	if not frappe.db.exists("Workspace", "HR Setup"):
		return

	ws = frappe.get_doc("Workspace", "HR Setup")
	changed = False

	# ── 1. Main-content links (powers the card grid) ─────────────────────
	existing_links = {lnk.link_to for lnk in ws.links if lnk.link_to}
	if not ("Employee Schedule" in existing_links and "Employee Holiday" in existing_links):
		changed = True
		_patch_links(ws, existing_links)

	# ── 2. Content JSON (positions the card widget in the layout) ─────────
	try:
		content = json.loads(ws.content or "[]")
	except Exception:
		content = []

	if not any(
		c.get("type") == "card" and c.get("data", {}).get("card_name") == "Scheduling"
		for c in content
	):
		changed = True
		leaves_idx = next(
			(
				i
				for i, c in enumerate(content)
				if c.get("type") == "card" and c.get("data", {}).get("card_name") == "Leaves"
			),
			None,
		)
		new_card = {"id": "sched_card_hrms", "type": "card", "data": {"card_name": "Scheduling", "col": 4}}
		if leaves_idx is not None:
			content.insert(leaves_idx + 1, new_card)
		else:
			content.append(new_card)
		ws.content = json.dumps(content)

	# ── 3. Shortcuts (powers the left-sidebar navigation) ─────────────────
	existing_shortcuts = {s.link_to for s in ws.shortcuts if s.link_to}
	if not ("Employee Schedule" in existing_shortcuts and "Employee Holiday" in existing_shortcuts):
		changed = True
		_patch_shortcuts(ws, existing_shortcuts)

	if not changed:
		return

	ws.save(ignore_permissions=True)
	frappe.db.commit()
	frappe.logger().info("HRMS: patched HR Setup workspace with Scheduling section")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _patch_links(ws, existing_links):
	"""Insert the Scheduling Card Break + two DocType links after the Leaves section."""
	# Find insertion point: just before the section that follows "Leaves"
	insert_idx = len(ws.links)
	in_leaves = False
	for i, lnk in enumerate(ws.links):
		if lnk.type == "Card Break" and lnk.label == "Leaves":
			in_leaves = True
			continue
		if in_leaves and lnk.type == "Card Break":
			insert_idx = i
			break

	new_rows = []
	if not any(lnk.label == "Scheduling" and lnk.type == "Card Break" for lnk in ws.links):
		new_rows.append(frappe._dict(
			hidden=0, is_query_report=0, label="Scheduling",
			link_count=2, onboard=0, type="Card Break",
		))

	if "Employee Schedule" not in existing_links:
		new_rows.append(frappe._dict(
			hidden=0, is_query_report=0, label="Employee Schedule",
			link_count=0, link_to="Employee Schedule",
			link_type="DocType", onboard=1, type="Link",
		))

	if "Employee Holiday" not in existing_links:
		new_rows.append(frappe._dict(
			hidden=0, is_query_report=0, label="Employee Holiday",
			link_count=0, link_to="Employee Holiday",
			link_type="DocType", onboard=1, type="Link",
		))

	for offset, row in enumerate(new_rows):
		ws.links.insert(insert_idx + offset, frappe.get_doc(dict(doctype="Workspace Link", **row)))


def _patch_shortcuts(ws, existing_shortcuts):
	"""Add sidebar shortcuts for Employee Schedule and Employee Holiday."""
	# Find a good insertion point: after the last existing shortcut whose
	# link_to is one of the "Leaves" doctypes, or append at the end.
	leaves_doctypes = {"Leave Application", "Compensatory Leave Request"}
	insert_idx = len(ws.shortcuts)
	for i, s in enumerate(ws.shortcuts):
		if s.link_to in leaves_doctypes:
			insert_idx = i + 1

	new_shortcuts = []
	if "Employee Schedule" not in existing_shortcuts:
		new_shortcuts.append(frappe._dict(
			label="Employee Schedule",
			link_to="Employee Schedule",
			type="DocType",
			icon="calendar",
			color="Grey",
		))

	if "Employee Holiday" not in existing_shortcuts:
		new_shortcuts.append(frappe._dict(
			label="Employee Holiday",
			link_to="Employee Holiday",
			type="DocType",
			icon="sun",
			color="Grey",
		))

	for offset, row in enumerate(new_shortcuts):
		ws.shortcuts.insert(
			insert_idx + offset,
			frappe.get_doc(dict(doctype="Workspace Shortcut", **row)),
		)
