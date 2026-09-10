"""
Post-migrate hooks for HRMS customisations.
Each function is called by Frappe after every `bench migrate`.
"""

import json

import frappe

_SCHEDULING_DOCTYPES = ("Employee Schedule", "Employee Holiday")


def add_scheduling_to_hr_setup_workspace():
	"""
	Ensure Employee Schedule and Employee Holiday appear in the HR Setup
	workspace — both in the main-content card area AND in the left sidebar.

	We patch the live database record rather than relying on JSON file
	sync, which silently skips files whose modified timestamp is older
	than the record already in the database.  The function is idempotent.
	"""
	if not frappe.db.exists("Workspace", "HR Setup"):
		return

	ws = frappe.get_doc("Workspace", "HR Setup")
	changed = False

	# ── 1. Main-content links (powers the card grid) ─────────────────────
	existing_links = {lnk.link_to for lnk in ws.links if lnk.link_to}
	missing_links = [d for d in _SCHEDULING_DOCTYPES if d not in existing_links]
	if missing_links:
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
		content.insert(leaves_idx + 1, new_card) if leaves_idx is not None else content.append(new_card)
		ws.content = json.dumps(content)

	# ── 3. Shortcuts (powers the left-sidebar navigation) ─────────────────
	existing_shortcuts = {s.link_to for s in ws.shortcuts if s.link_to}
	missing_shortcuts = [d for d in _SCHEDULING_DOCTYPES if d not in existing_shortcuts]
	if missing_shortcuts:
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
	for doctype in _SCHEDULING_DOCTYPES:
		if doctype not in existing_links:
			new_rows.append(frappe._dict(
				hidden=0, is_query_report=0, label=doctype,
				link_count=0, link_to=doctype,
				link_type="DocType", onboard=1, type="Link",
			))

	for offset, row in enumerate(new_rows):
		# frappe.get_doc on a child doctype wires up parent/child correctly
		# when the parent document already has it in its child list.
		ws.links.insert(insert_idx + offset, frappe.get_doc(dict(doctype="Workspace Link", **row)))


def _patch_shortcuts(ws, existing_shortcuts):
	"""
	Add sidebar shortcuts for Employee Schedule and Employee Holiday.

	IMPORTANT: use ws.append() — NOT ws.shortcuts.insert() with frappe.get_doc().
	ws.append() is the correct Frappe API: it sets parent/parentfield/parenttype
	on the child row so it is persisted when the parent is saved.  Inserting a
	bare frappe.get_doc() result into an empty child-table list leaves those
	attributes unset and the rows are silently dropped at save time.
	"""
	icons = {"Employee Schedule": "calendar", "Employee Holiday": "sun"}

	for doctype in _SCHEDULING_DOCTYPES:
		if doctype not in existing_shortcuts:
			ws.append("shortcuts", {
				"type": "DocType",
				"link_to": doctype,
				"label": doctype,
				"icon": icons.get(doctype, "file"),
				"color": "Grey",
				"doc_view": "",
			})
