import pathlib
import subprocess
import unittest

SCRIPT = pathlib.Path(__file__).with_name("deploy.sh")


class DeploymentRecoveryTests(unittest.TestCase):
    def cache_clear(self, codes):
        source = SCRIPT.read_text()
        block = source[source.index("CACHE_CLEARED=0"):source.index('OPS="$OPS|clear-cache"')]
        stub = """
set -e
attempt=0
codes=(%s)
cx() { local status=${codes[$attempt]}; attempt=$((attempt + 1)); echo attempted >&2; return "$status"; }
sleep() { :; }
fail() { echo "$*" >&2; exit 1; }
""" % " ".join(map(str, codes))
        return subprocess.run(["bash", "-c", stub + block], capture_output=True, text=True)

    def test_invalid_recovery_id_rejected_before_server_access(self):
        result = subprocess.run(["bash", str(SCRIPT), "--previous-override-from", "../invalid"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact deployment id", result.stderr)

    def test_cache_connection_failure_is_retried(self):
        result = self.cache_clear([255, 0])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count("attempted"), 2)

    def test_cache_application_failure_is_not_retried(self):
        result = self.cache_clear([1, 0])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr.count("attempted"), 1)

    def test_connection_retries_are_bounded(self):
        result = self.cache_clear([255, 255, 255, 0])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr.count("attempted"), 3)
