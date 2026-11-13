"""Validate the private, deployment-bound acceptance receipt from the live harness."""

from datetime import datetime, timezone
import hashlib
import json

from .errors import SetupError
from .private_files import read_json

COMMON_CHECKS = {
    "runtime_grants", "database_cache", "loan_issue_return", "event_registration",
    "private_upload", "browser_cors", "outbox_delivery", "polling", "mandatory_encryption",
    "generated_credential_policy",
}
FULL_CHECKS = {"worker_task_roundtrip", "scheduler_progress", "full_binaries", "full_profile_isolation"}
FREE_CHECKS = {"tick_auth", "tick_progress", "tick_overlap", "single_web_512mb", "free_quotas", "full_profile_isolation"}


def configuration_hash(values):
    # A hash binds evidence to secrets/config without persisting their values in
    # the receipt. This private receipt must not be published as a public artifact.
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_acceptance(path, values, answers):
    if not path:
        raise SetupError("runtime_acceptance_required", "Run the deployed acceptance checks and supply their private receipt with --acceptance-file.")
    report = read_json(path)
    required = {"version", "deployment_id", "backend_image", "configuration_sha256", "profile", "checked_at", "checks"}
    if set(report) != required or report["version"] != 1:
        raise SetupError("acceptance_format", "Use the version-1 live acceptance receipt contract in deploy/cloud/acceptance-contract.json.")
    if any((report["deployment_id"] != values.get("SPACEWORKS_DEPLOYMENT_ID"), report["backend_image"] != answers["backend_image"], report["configuration_sha256"] != configuration_hash(values), report["profile"] != answers["profile"])):
        raise SetupError("acceptance_mismatch", "Rerun deployed acceptance against this exact deployment, image, profile and private configuration.")
    try:
        checked = datetime.fromisoformat(report["checked_at"])
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        if not 0 <= age <= 3600:
            raise ValueError
    except (TypeError, ValueError):
        raise SetupError("acceptance_stale", "Provide timezone-aware acceptance evidence from the last hour.") from None
    checks = report["checks"]
    expected = COMMON_CHECKS | (FREE_CHECKS if answers["profile"] == "free" else FULL_CHECKS)
    if answers.get("scan_policy") == "external":
        expected |= {"external_scanner_signature_stream_limits"}
    if not isinstance(checks, dict) or not expected <= checks.keys() or any(checks[key] != "passed" for key in expected):
        raise SetupError("runtime_acceptance_failed", "Complete every required live check; health, process existence and YAML parsing alone cannot satisfy acceptance.")
    return {"status": "passed", "source": "operator-owned-live-harness-receipt", "receipt_sha256": hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()}
