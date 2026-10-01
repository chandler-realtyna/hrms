import unittest
from types import SimpleNamespace

from hrms.patches.v16_0.create_company_director_access import ROLE_PROFILE, _attach_director_profile


class ProfileUser:
	def __init__(self, profiles):
		self.role_profiles = [SimpleNamespace(role_profile=name) for name in profiles]
		self.saves = 0

	def append(self, field, row):
		assert field == "role_profiles"
		self.role_profiles.append(SimpleNamespace(**row))

	def save(self, **kwargs):
		assert kwargs == {"ignore_permissions": True}
		self.saves += 1


class TestDirectorProfiles(unittest.TestCase):
	def test_existing_profiles_are_preserved(self):
		user = ProfileUser(["Accounts", "Project Manager"])
		_attach_director_profile(user)
		self.assertEqual([row.role_profile for row in user.role_profiles], ["Accounts", "Project Manager", ROLE_PROFILE])
		self.assertEqual(user.saves, 1)

	def test_attachment_is_idempotent(self):
		user = ProfileUser([ROLE_PROFILE])
		_attach_director_profile(user)
		self.assertEqual(len(user.role_profiles), 1)
		self.assertEqual(user.saves, 0)
