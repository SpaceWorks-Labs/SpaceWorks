"""Finite release and completion transitions, without invoking Django/services."""

from contextlib import ExitStack
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.bootstrap import bootstrap, release
from cloud_setup.errors import SetupError


class BootstrapTests(unittest.TestCase):
    def run_bootstrap(self, **options):
        with ExitStack() as stack:
            mocks = {}
            for name, value in {
                "validate": {"status": "passed", "checks": []}, "release": {"status": "passed"},
                "storage_probe": {"status": "passed"}, "readiness": {"status": "passed"},
                "send_in_environment": {"status": "passed", "send": "accepted"}, "write_json": None,
            }.items():
                mocks[name] = stack.enter_context(patch("cloud_setup.bootstrap." + name, return_value=value))
            receipt = stack.enter_context(patch("cloud_setup.completion.verify_acceptance", return_value={"status": "passed"}))
            if options.pop("fail_release", False):
                mocks["release"].side_effect = SetupError("release_failed", "Retry privately.")
            if options.pop("fail_receipt", False):
                receipt.side_effect = SetupError("runtime_acceptance_failed", "Run required flows.")
            result = bootstrap("/private/state", {}, {"api_origin": "https://api.example.com"}, **options)
            return result, mocks

    def test_initial_release_is_finite_and_never_complete(self):
        report, mocks = self.run_bootstrap(release_only=True)
        self.assertEqual(report["status"], "released")
        mocks["storage_probe"].assert_not_called()
        mocks["readiness"].assert_not_called()

    def test_release_failure_prevents_downstream_effects(self):
        report, mocks = self.run_bootstrap(fail_release=True, send_test=True)
        self.assertEqual(report["status"], "incomplete")
        mocks["storage_probe"].assert_not_called()
        mocks["send_in_environment"].assert_not_called()

    def test_provider_acceptance_without_inbox_confirmation_incomplete(self):
        report, mocks = self.run_bootstrap(send_test=True)
        self.assertEqual(report["status"], "incomplete")
        mocks["send_in_environment"].assert_called_once()

    def test_no_send_when_not_explicitly_requested(self):
        report, mocks = self.run_bootstrap(inbox_confirmed=True)
        self.assertEqual(report["status"], "incomplete")
        mocks["send_in_environment"].assert_not_called()

    def test_real_harness_failure_never_marks_complete(self):
        report, _ = self.run_bootstrap(send_test=True, inbox_confirmed=True, fail_receipt=True)
        self.assertEqual(report["status"], "incomplete")

    def test_completion_requires_all_checks_send_and_inbox(self):
        report, _ = self.run_bootstrap(send_test=True, inbox_confirmed=True)
        self.assertEqual(report["status"], "complete")

    def test_release_uses_frozen_argv_and_hides_process_output(self):
        with patch("cloud_setup.bootstrap.subprocess.run") as process:
            release({"DATABASE_MAINTENANCE_URL": "never-log-me"})
        args, kwargs = process.call_args
        self.assertIn("--role", args[0])
        self.assertEqual(args[0][-1], "release")
        self.assertNotIn("never-log-me", str(args))
        self.assertEqual(kwargs["env"]["DATABASE_MAINTENANCE_URL"], "never-log-me")
        self.assertEqual(kwargs["timeout"], 1800)
        self.assertTrue(kwargs["check"])


if __name__ == "__main__":
    unittest.main()
