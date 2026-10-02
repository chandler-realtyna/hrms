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

    def test_verified_raw_desk_assets_require_activation_not_build(self):
        for path in plan.RAW_DESK_ASSETS:
            with self.subTest(path=path):
                self.assertEqual(self.classify_path(path), "frontend")

    def test_other_public_sources_still_require_full_build(self):
        for path in (
            "hrms/public/js/hrms.bundle.js",
            "hrms/public/js/unverified.js",
            "hrms/public/css/unverified.css",
            "hrms/public/scss/hrms.bundle.scss",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.classify_path(path), "full")

    def test_raw_assets_never_skip_schema_migration(self):
        paths = ["hrms/hooks.py", *sorted(plan.RAW_DESK_ASSETS)]
        diff = "".join(f"M\0{path}\0" for path in paths)
        with patch.object(plan, "_git", side_effect=["commit", "commit", diff]):
            result = plan.classify(".", "previous", "candidate")
        self.assertEqual(result["class"], "schema")
        self.assertEqual(result["counts"]["schema"], 1)
        self.assertEqual(result["counts"]["frontend"], 3)
