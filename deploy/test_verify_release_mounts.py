import copy
import unittest
from verify_release_mounts import SERVICES, verify


class ReleaseMountTests(unittest.TestCase):
    def setUp(self):
        self.release = "/srv/hrms-releases/exact-sha"
        self.containers = [{
            "Config": {"Labels": {"com.docker.compose.service": service}},
            "State": {"Running": True},
            "Mounts": [{"Destination": "/home/frappe/frappe-bench/apps/hrms", "Source": self.release},
                       {"Destination": "/home/frappe/frappe-bench/assets/hrms", "Source": self.release + "/hrms/public"}],
        } for service in sorted(SERVICES)]

    def test_exact_source_and_assets(self):
        verify(self.containers, self.release)

    def test_missing_service(self):
        with self.assertRaises(ValueError):
            verify(self.containers[:-1], self.release)

    def test_duplicate_service(self):
        with self.assertRaises(ValueError):
            verify(self.containers + [copy.deepcopy(self.containers[0])], self.release)

    def test_stopped_service(self):
        self.containers[0]["State"]["Running"] = False
        with self.assertRaises(ValueError):
            verify(self.containers, self.release)

    def test_previous_source(self):
        self.containers[0]["Mounts"][0]["Source"] = "/srv/hrms-releases/previous"
        with self.assertRaises(ValueError):
            verify(self.containers, self.release)

    def test_previous_assets(self):
        self.containers[0]["Mounts"][1]["Source"] = "/srv/hrms-releases/previous/hrms/public"
        with self.assertRaises(ValueError):
            verify(self.containers, self.release)
