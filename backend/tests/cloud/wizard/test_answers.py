"""Local-only setup boundary tests; no Django/database initialization."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.answers import validate_answers
from cloud_setup.environment import effective_environment, role_environment
from cloud_setup.errors import SetupError


def answers(free=False):
    name = "free.answers.example.json" if free else "answers.example.json"
    value = json.loads((ROOT / "deploy/cloud" / name).read_text())
    value["backend_image"] = "ghcr.io/spaceworks-labs/spaceworks-backend@sha256:" + "a" * 64
    if free:
        value["free"]["checked_on"] = date.today().isoformat()
    return value


class AnswerTests(unittest.TestCase):
    def test_full_and_free_are_explicit(self):
        for free in (False, True):
            validate_answers(answers(free))

    def test_unknown_missing_and_boolean_versions_refused(self):
        for mutation in (lambda a: a.update(typo=1), lambda a: a.pop("profile"), lambda a: a.update(version=True)):
            value = answers()
            mutation(value)
            with self.assertRaises(SetupError):
                validate_answers(value)

    def test_unverified_zero_digest_refused(self):
        value = answers()
        value["backend_image"] = value["backend_image"][:-64] + "0" * 64
        with self.assertRaises(SetupError):
            validate_answers(value)

    def test_transaction_and_wildcard_hosts_refused(self):
        for key, item in (("database_connection_mode", "transaction"), ("allowed_hosts", ["*"]), ("allowed_hosts", [".example.com"])):
            value = answers()
            value[key] = item
            with self.assertRaises(SetupError):
                validate_answers(value)

    def test_credentials_in_answers_refused(self):
        for key in ("DATABASE_URL", "FREE_TICK_SECRET", "AWS_SECRET_ACCESS_KEY", "PII_MASTER_KEY", "CELERY_BROKER_URL", "CACHE_URL", "LIVE_REDIS_URL", "CELERY_RESULT_BACKEND"):
            value = answers()
            value["environment"][key] = "secret-sentinel"
            with self.assertRaises(SetupError) as raised:
                validate_answers(value)
            self.assertNotIn("secret-sentinel", str(raised.exception))

    def test_free_requires_current_caps_and_explicit_consent(self):
        for field, item in (("db_cap_bytes", 0), ("email_daily_cap", True), ("checked_on", "2020-01-01"), ("acknowledge_limits", False), ("tick_interval_seconds", 60)):
            value = answers(True)
            value["free"][field] = item
            with self.assertRaises(SetupError):
                validate_answers(value)

    def test_neon_uses_slower_explicit_free_tick(self):
        value = answers(True)
        value["database_provider"] = "neon"
        with self.assertRaises(SetupError):
            validate_answers(value)
        value["free"]["tick_interval_seconds"] = 1800
        validate_answers(value)

    def test_free_never_leaks_into_full(self):
        full = effective_environment(answers(), {})
        free = effective_environment(answers(True), {})
        self.assertFalse(any(key.startswith("FREE_") for key in full))
        self.assertEqual(full["CLOUD_SCHEDULER"], "beat")
        self.assertEqual(free["CLOUD_SCHEDULER"], "tick")
        self.assertEqual(free["GUNICORN_WORKERS"], "1")
        self.assertEqual(free["CELERY_BROKER_URL"], "")

    def test_contradictory_env_and_secret_settings_refused(self):
        value = answers(True)
        value["environment"]["CLOUD_SCHEDULER"] = "loop"
        with self.assertRaises(SetupError):
            effective_environment(value, {})
        with self.assertRaises(SetupError):
            effective_environment(answers(True), {"CELERY_BROKER_URL": "rediss://invalid"})

    def test_release_credentials_never_reach_residents(self):
        values = effective_environment(answers(), {
            "DATABASE_URL": "runtime", "DATABASE_MAINTENANCE_URL": "owner",
            "CLOUD_SCRATCH_DATABASES_FILE": "/private/scratch.json", "SETUP_SUPERADMIN_PASSWORD": "sentinel",
        })
        for role in ("web", "live", "worker", "beat", "scheduler"):
            runtime = role_environment(values, role)
            self.assertEqual(runtime["DATABASE_URL"], "runtime")
            self.assertNotIn("DATABASE_MAINTENANCE_URL", runtime)
            self.assertFalse(any(k.startswith("SETUP_") for k in runtime))
        self.assertEqual(role_environment(values, "release")["DATABASE_MAINTENANCE_URL"], "owner")

    def test_existing_pii_options_remain_configurable(self):
        value = answers()
        value["environment"].update(PII_ENCRYPTION_ENABLED="True", PII_KEY_BROKER="aws_kms", PII_DEK_CACHE_TTL_SECONDS="120")
        result = effective_environment(value, {})
        self.assertEqual(result["PII_KEY_BROKER"], "aws_kms")
        self.assertEqual(result["PII_ENCRYPTION_ENABLED"], "True")
        value["environment"]["CRON_INTERVAL_SECONDS"] = "300"
        with self.assertRaises(SetupError):
            effective_environment(value, {})


if __name__ == "__main__":
    unittest.main()
