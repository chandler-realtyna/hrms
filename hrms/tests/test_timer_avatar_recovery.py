"""Synthetic QA-only checks for conflict recovery and authenticated thumbnails."""
import io
import unittest
from datetime import timedelta
from uuid import uuid4

import frappe
from PIL import Image

from hrms.api import timer_state as timer, weekly_timesheet as week
from hrms.api.profile_photo import directory_image, get_photo
from hrms.tests import test_shared_work_state as shared


class TestTimerAvatarRecovery(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		shared.TestSharedWorkState.setUpClass()
		cls.users = shared.TestSharedWorkState.users
		cls.employees = shared.TestSharedWorkState.employees
		cls.projects = shared.TestSharedWorkState.projects

	setUp = shared.TestSharedWorkState.setUp
	tearDown = shared.TestSharedWorkState.tearDown
	act = shared.TestSharedWorkState.act
	draft = shared.TestSharedWorkState.draft

	def test_conflict_preview_is_own_scope_and_does_not_change_timer(self):
		name = self.draft()["name"]
		self.act("start", {"project": self.projects[0]})
		self.now += timedelta(minutes=10)
		self.act("pause")
		state = timer.get_state()
		local_start = timer._date(state["timer"]["segments"][0]["from"]).astimezone(
			timer.ZoneInfo(timer.get_system_timezone())).replace(tzinfo=None)
		frappe.db.set_value("Timesheet Detail", {"parent": name}, {
			"from_time": local_start, "to_time": local_start + timedelta(minutes=20),
		})
		preview = timer.get_save_conflicts(self.projects[0])
		self.assertEqual(len(preview["rows"]), 1)
		self.assertEqual(preview["rows"][0]["timesheet"], name)
		self.assertEqual(timer.get_state()["timer"], state["timer"])
		self.assertEqual(timer.get_state()["revision"], state["revision"])
		with self.assertRaises(frappe.ValidationError):
			self.act("save", {"project": self.projects[0]})
		self.assertEqual(timer.get_state()["timer"], state["timer"])
		frappe.set_user(self.users[1])
		self.assertEqual(timer.get_save_conflicts()["rows"], [])

	def test_subminute_rows_do_not_create_false_minute_overlap(self):
		doc = frappe.get_doc("Timesheet", self.draft()["name"])
		doc.append("time_logs", dict(project=self.projects[0], activity_type="Unassigned",
			from_time="2026-09-28 09:30:10", to_time="2026-09-28 09:30:20"))
		week._validate_time_rows(doc)

	def test_nested_overlap_remains_detected(self):
		doc = frappe.get_doc("Timesheet", self.draft()["name"])
		for start, end in [("09:10", "09:20"), ("09:30", "09:40")]:
			doc.append("time_logs", dict(project=self.projects[0], activity_type="Unassigned",
				from_time="2026-09-28 " + start, to_time="2026-09-28 " + end))
		with self.assertRaises(frappe.ValidationError) as error:
			week._validate_time_rows(doc)
		self.assertIn("maximum is 5 minutes", str(error.exception))

	def photo(self):
		frappe.set_user(self.users[2])
		out = io.BytesIO()
		image = Image.new("RGB", (300, 200), "green")
		# Isolate file deduplication from persistent browser fixtures on this QA site.
		image.putpixel((0, 0), tuple(uuid4().bytes[:3]))
		image.save(out, format="PNG")
		file = frappe.get_doc(dict(doctype="File", file_name="qa-directory-photo-" + uuid4().hex + ".png",
			is_private=1, content=out.getvalue(), attached_to_doctype="Employee",
			attached_to_name=self.employees[1], attached_to_field="image")).insert(ignore_permissions=True)
		frappe.db.set_value("Employee", self.employees[1], "image", file.file_url)
		frappe.set_user(self.users[0])
		return file

	def test_authenticated_directory_thumbnail_without_original_file_permission(self):
		file = self.photo()
		self.assertFalse(frappe.has_permission("Employee", "read", doc=frappe.get_doc("Employee", self.employees[1])))
		url = directory_image(self.employees[1], file.file_url)
		self.assertIn("hrms.api.profile_photo.get_photo?", url)
		self.assertNotIn(file.file_url, url)
		response = get_photo(self.employees[1])
		self.assertEqual(response.mimetype, "image/webp")
		self.assertEqual(Image.open(io.BytesIO(response.data)).size, (128, 128))
		self.assertEqual(response.headers["Cache-Control"], "private, no-store")
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_photo(self.employees[1])

	def test_thumbnail_rejects_inactive_or_unlinked_private_file(self):
		file = self.photo()
		frappe.db.set_value("Employee", self.employees[1], "status", "Left")
		with self.assertRaises(frappe.DoesNotExistError): get_photo(self.employees[1])
		frappe.db.set_value("Employee", self.employees[1], "status", "Active")
		frappe.db.set_value("File", file.name, "attached_to_name", self.employees[2])
		with self.assertRaises(frappe.DoesNotExistError): get_photo(self.employees[1])
		self.assertEqual(directory_image(self.employees[1], "/files/public.png"), "/files/public.png")
