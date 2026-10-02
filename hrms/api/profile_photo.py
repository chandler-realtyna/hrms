"""Authenticated directory thumbnails, never a general private-file proxy."""
import hashlib
import io

import frappe
from frappe import _
from werkzeug.wrappers import Response


def directory_image(employee, image):
	if not image or not image.startswith("/private/files/"):
		return image or ""
	from urllib.parse import urlencode
	return "/api/method/hrms.api.profile_photo.get_photo?" + urlencode({
		"employee": employee, "version": hashlib.sha256(image.encode()).hexdigest()[:16],
	})


@frappe.whitelist(methods=["GET"])
def get_photo(employee, version=None):
	from PIL import Image, ImageOps
	from hrms.utils.personal_scope import _is_manager
	user = frappe.session.user
	if user == "Guest" or not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("Sign in to view profile pictures."), frappe.PermissionError)
	if not _is_manager(user) and not frappe.db.exists("Employee", {"user_id": user, "status": "Active"}):
		frappe.throw(_("Profile directory access is not available."), frappe.PermissionError)
	person = frappe.db.get_value("Employee", {"name": employee, "status": "Active"}, ["image", "user_id"], as_dict=True)
	if not person or not person.image or not person.image.startswith("/private/files/"):
		frappe.throw(_("Profile picture not found."), frappe.DoesNotExistError)
	files = frappe.get_all("File", filters={"file_url": person.image, "is_private": 1},
		fields=["name", "attached_to_doctype", "attached_to_name", "file_size"])
	linked = next((file for file in files if
		(file.attached_to_doctype == "Employee" and file.attached_to_name == employee) or
		(person.user_id and file.attached_to_doctype == "User" and file.attached_to_name == person.user_id)), None)
	if not linked or not linked.file_size or linked.file_size > 8 * 1024 * 1024:
		frappe.throw(_("Profile picture is unavailable."), frappe.DoesNotExistError)
	content = frappe.get_doc("File", linked.name).get_content()
	if not isinstance(content, bytes) or len(content) > 8 * 1024 * 1024:
		frappe.throw(_("Profile picture is unavailable."), frappe.DoesNotExistError)
	try:
		with Image.open(io.BytesIO(content)) as source:
			if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 16_000_000:
				raise ValueError("Unsupported profile image")
			image = ImageOps.fit(ImageOps.exif_transpose(source), (128, 128)).convert("RGB")
			out = io.BytesIO()
			image.save(out, format="WEBP", quality=80)
	except (OSError, ValueError, Image.DecompressionBombError):
		frappe.throw(_("Profile picture could not be read."), frappe.DoesNotExistError)
	return Response(out.getvalue(), mimetype="image/webp", headers={
		"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
	})
