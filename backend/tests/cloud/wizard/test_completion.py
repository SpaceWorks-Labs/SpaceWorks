"""Completion must be fresh, deployment-bound and based on actual harness results."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.completion import COMMON_CHECKS, FREE_CHECKS, FULL_CHECKS, configuration_hash, verify_acceptance
from cloud_setup.errors import SetupError


class CompletionTests(unittest.TestCase):
    def receipt(self, profile="free"):
        values = {"SPACEWORKS_DEPLOYMENT_ID": "deployment-id", "SECRET_KEY": "never-print"}
        answers = {"backend_image": "image@sha256:digest", "profile": profile}
        report = {"version": 1, "deployment_id": "deployment-id", "backend_image": answers["backend_image"], "configuration_sha256": configuration_hash(values), "profile": profile, "checked_at": datetime.now(timezone.utc).isoformat(), "checks": {key: "passed" for key in COMMON_CHECKS | (FREE_CHECKS if profile == "free" else FULL_CHECKS)}}
        return report, values, answers

    def test_valid_full_and_free_receipts(self):
        for profile in ("full", "free"):
            report, values, answers = self.receipt(profile)
            with patch("cloud_setup.completion.read_json", return_value=report):
                result = verify_acceptance("/private/receipt.json", values, answers)
            self.assertEqual(result["status"], "passed")
            self.assertNotIn("never-print", str(result))

    def test_missing_receipt_never_completes(self):
        with self.assertRaises(SetupError):
            verify_acceptance(None, {}, {})

    def test_old_wrong_identity_image_config_profile_refused(self):
        for field, item in (("deployment_id", "other"), ("backend_image", "other"), ("configuration_sha256", "other"), ("profile", "full"), ("checked_at", (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())):
            report, values, answers = self.receipt()
            report[field] = item
            with patch("cloud_setup.completion.read_json", return_value=report), self.assertRaises(SetupError):
                verify_acceptance("/private/report.json", values, answers)

    def test_unexecuted_or_failed_core_flow_refused(self):
        for value in ("failed", "skipped", "unknown"):
            report, values, answers = self.receipt()
            report["checks"]["loan_issue_return"] = value
            with patch("cloud_setup.completion.read_json", return_value=report), self.assertRaises(SetupError):
                verify_acceptance("/private/report.json", values, answers)

    def test_selected_scanner_requires_real_scan_and_signature_evidence(self):
        report, values, answers = self.receipt()
        answers["scan_policy"] = "external"
        with patch("cloud_setup.completion.read_json", return_value=report), self.assertRaises(SetupError):
            verify_acceptance("/private/report.json", values, answers)
        report["checks"]["external_scanner_signature_stream_limits"] = "passed"
        with patch("cloud_setup.completion.read_json", return_value=report):
            self.assertEqual(verify_acceptance("/private/report.json", values, answers)["status"], "passed")


if __name__ == "__main__":
    unittest.main()
