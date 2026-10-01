import unittest
from unittest.mock import patch

import plan


class TestReleaseProxyClassification(unittest.TestCase):
    def classify_path(self, path):
        with patch.object(plan, "_git", side_effect=["commit", "commit", f"M\0{path}\0"]):
            return plan.classify(".", "previous", "candidate")["class"]

    def test_proxy_config_requires_activation(self):
        self.assertEqual(self.classify_path("deploy/nginx.conf"), "frontend")

    def test_documentation_does_not_require_activation(self):
        self.assertEqual(self.classify_path("deploy/README.md"), "none")

    def test_unknown_infrastructure_is_still_full(self):
        self.assertEqual(self.classify_path("new-infrastructure/proxy.conf"), "full")

    def test_hook_changes_still_require_migration(self):
        self.assertEqual(self.classify_path("hrms/hooks.py"), "schema")
