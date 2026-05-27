"""
Post-migrate hooks for HRMS customisations.
Each function is called by Frappe after every `bench migrate`.
"""

import frappe


def add_scheduling_to_hr_setup_workspace():
	"""
	Ensure Employee Schedule and Employee Holiday appear in the HR Setup
	workspace under a "Scheduling" section.

	We patch the live database record rather than relying on JSON file
	sync, which can silently skip files whose modified timestamp is older
	than the record already in the database.
	"""
	if not frappe.db.exists("Workspace", "HR Setup"):
		return

	ws = frappe.get_doc("Workspace", "HR Setup")

	# Check if we've already added these links
	existing = {lnk.link_to for lnk in ws.links if lnk.link_to}
	if "Employee Schedule" in existing and "Employee Holiday" in existing:
		return  # nothing to do

	# ── Find insertion point ─────────────────────────────────────────────
	# Insert the Scheduling card right after the Leaves card-break section.
	# We look for the last link that belongs to "Leaves" (Compensatory Leave
	# Request) and insert after it.  Fall back to appending at the end if the
	# section can't be found.
	insert_idx = len(ws.links)  # default: append
	in_leaves = False
	for i, lnk in enumerate(ws.links):
		if lnk.type == "Card Break" and lnk.label == "Leaves":
			in_leaves = True
			continue
		if in_leaves and lnk.type == "Card Break":
			# Hit the next section — insert just before it
			insert_idx = i
			break

	# ── Build new rows ───────────────────────────────────────────────────
	new_rows = []

	if not any(lnk.label == "Scheduling" and lnk.type == "Card Break" for lnk in ws.links):
		new_rows.append(
			frappe._dict(
				hidden=0,
				is_query_report=0,
				label="Scheduling",
				link_count=2,
				onboard=0,
				type="Card Break",
			)
		)

	if "Employee Schedule" not in existing:
		new_rows.append(
			frappe._dict(
				hidden=0,
				is_query_report=0,
				label="Employee Schedule",
				link_count=0,
				link_to="Employee Schedule",
				link_type="DocType",
				onboard=1,
				type="Link",
			)
		)

	if "Employee Holiday" not in existing:
		new_rows.append(
			frappe._dict(
				hidden=0,
				is_query_report=0,
				label="Employee Holiday",
				link_count=0,
				link_to="Employee Holiday",
				link_type="DocType",
				onboard=1,
				type="Link",
			)
		)

	if not new_rows:
		return

	# Splice the new rows into the link list
	for offset, row in enumerate(new_rows):
		ws.links.insert(insert_idx + offset, frappe.get_doc(dict(doctype="Workspace Link", **row)))

	# ── Update the content JSON (adds the Scheduling card widget) ────────
	import json

	try:
		content = json.loads(ws.content or "[]")
	except Exception:
		content = []

	if not any(
		c.get("type") == "card" and c.get("data", {}).get("card_name") == "Scheduling"
		for c in content
	):
		# Insert after the "Leaves" card
		leaves_idx = next(
			(
				i
				for i, c in enumerate(content)
				if c.get("type") == "card" and c.get("data", {}).get("card_name") == "Leaves"
			),
			None,
		)
		new_card = {
			"id": "sched_card_hrms",
			"type": "card",
			"data": {"card_name": "Scheduling", "col": 4},
		}
		if leaves_idx is not None:
			content.insert(leaves_idx + 1, new_card)
		else:
			content.append(new_card)
		ws.content = json.dumps(content)

	ws.save(ignore_permissions=True)
	frappe.db.commit()
	frappe.logger().info("HRMS: patched HR Setup workspace with Scheduling section")
