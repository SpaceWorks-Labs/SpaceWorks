"""Local-only identity admission and full/free finite-command regressions."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from apps.backup.host_marker import DatabaseIdentity, MarkerStage
from apps.backup.privileged_target import expected_target, privileged_url, verify_target
from apps.backup.managed.profile import DeploymentProfile, validate_process

IDENTITY = "11111111-2222-3333-4444-555555555555"
RUNTIME = "postgresql://app:narrow@runtime.example:5432/sibling_b?sslmode=require"
MAINTENANCE = "postgresql://owner:protected@owner.example:5433/original_a?sslmode=verify-full&sslrootcert=%2Ftrust%2Froot.pem"


class Database:
    def __init__(self, name="sibling_b", oid=22, has_identity=True, populated=True):
        self.answers = iter([(name, oid), ("identity" if has_identity else None,), (populated,)])
        self.sql = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.sql.append(sql)

    def fetchone(self):
        return next(self.answers)


def marker(name="sibling_b", oid=22, identity=IDENTITY):
    return SimpleNamespace(stage=MarkerStage.BOUND, database=DatabaseIdentity(
        name, oid, {"database_uuid": identity} if identity else None))


def expected(**changes):
    values = {"SPACEWORKS_PRIVILEGED_TARGET_REQUIRED": "1", "SPACEWORKS_PRIVILEGED_TARGET_NAME": "sibling_b",
              "SPACEWORKS_PRIVILEGED_TARGET_OID": "22", "SPACEWORKS_PRIVILEGED_TARGET_UUID": IDENTITY}
    values.update(changes)
    return values


class TargetingTests(unittest.TestCase):
    def test_cutover_retargets_only_database_preserving_owner_and_tls(self):
        before, after = urlsplit(MAINTENANCE), urlsplit(privileged_url(MAINTENANCE, RUNTIME))
        self.assertEqual(after.path, "/sibling_b")
        self.assertEqual((after.scheme, after.netloc, after.query), (before.scheme, before.netloc, before.query))
        self.assertNotIn("narrow", after.geturl())

    def test_routing_override_refused(self):
        for runtime in (RUNTIME + "&dbname=original_a", RUNTIME + "#original_a"):
            with self.assertRaises(ValueError):
                privileged_url(MAINTENANCE, runtime)
        with self.assertRaises(ValueError):
            privileged_url(MAINTENANCE + "&dbname=original_a", RUNTIME)

    def test_exact_marker_and_protected_tuple_pass(self):
        live = SimpleNamespace(database_uuid=IDENTITY)
        with patch("apps.backup.privileged_target.query_live_database_identity", return_value=live):
            self.assertIs(verify_target(Database(), marker(), RUNTIME, expected()), live)

    def test_pointer_oid_uuid_and_stale_expected_proof_refuse_before_writes(self):
        with patch("apps.backup.privileged_target.query_live_database_identity", return_value=SimpleNamespace(database_uuid=IDENTITY)):
            for bound, values, name in ((marker(oid=21), expected(), "sibling_b"),
                                        (marker(), expected(SPACEWORKS_PRIVILEGED_TARGET_NAME="original_a"), "sibling_b"),
                                        (marker(identity="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"), expected(), "sibling_b"),
                                        (marker(), expected(), "original_a")):
                database = Database(name=name)
                with self.assertRaises(ValueError):
                    verify_target(database, bound, RUNTIME, values)
                self.assertTrue(all(sql.startswith("SELECT") for sql in database.sql))

    def test_partial_expected_proof_is_not_initial_bootstrap(self):
        for values in ({"SPACEWORKS_PRIVILEGED_TARGET_REQUIRED": "1"},
                       {"SPACEWORKS_PRIVILEGED_TARGET_NAME": "sibling_b"}):
            with self.assertRaises(ValueError):
                expected_target(values)
        with self.assertRaises(ValueError):
            verify_target(Database(has_identity=False), marker(), RUNTIME, {}, allow_initial=True)
        self.assertIsNone(verify_target(Database(has_identity=False), marker(identity=None), RUNTIME, {}, allow_initial=True))

    def test_missing_marker_cannot_adopt_populated_database_without_legacy_proof(self):
        with self.assertRaises(ValueError):
            verify_target(Database(), None, RUNTIME, {}, allow_initial=True)
        with patch("apps.backup.privileged_target.query_live_database_identity", return_value=SimpleNamespace(database_uuid=IDENTITY)):
            self.assertIsNotNone(verify_target(Database(), None, RUNTIME,
                {"SPACEWORKS_INITIALIZE_DATABASE_NAME": "sibling_b", "SPACEWORKS_INITIALIZE_DATABASE_OID": "22"}, allow_initial=True))
        self.assertIsNone(verify_target(Database(has_identity=False, populated=False), None, RUNTIME, {}, allow_initial=True))

    def test_finite_managed_work_and_storage_do_not_extend_free_resident_roles(self):
        fixed = ["python", "-m", "scripts.run_cloud_role"]
        validate_process(DeploymentProfile("managed", "full"), "worker", fixed + ["worker", "--once"])
        for profile in ("full", "free"):
            validate_process(DeploymentProfile("managed", profile), "management", ["python", "manage.py", "verify_storage", "--browser-probes"])
        with self.assertRaises(ValueError):
            validate_process(DeploymentProfile("managed", "free"), "worker", fixed + ["worker", "--once"])
        # Default/full host process vocabulary is unchanged by managed additions.
        validate_process(DeploymentProfile(), "worker", ["celery", "-A", "config", "worker"])


if __name__ == "__main__":
    unittest.main()
