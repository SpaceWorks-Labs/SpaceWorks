"""Endpoint contradictions, retained locks and secret-safe probe failures."""

import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.database_probe import database_probe, lock_probe, validate_endpoint
from cloud_setup.errors import SetupError
from cloud_setup.validation import probe


class ProbeTests(unittest.TestCase):
    def test_known_unsafe_poolers_and_plaintext_refused(self):
        for url, mode in (
            ("postgresql://app:p@db.test/app?sslmode=disable", "direct"),
            ("postgresql://app:p@pooler.supabase.com:6543/app?sslmode=require", "session"),
            ("postgresql://app:p@ep-demo-pooler.neon.tech/app?sslmode=require", "session"),
            ("postgresql://app:p@x.pooler.supabase.com:5432/app?sslmode=require", "direct"),
            ("postgresql://app:p@db.test/app?sslmode=require&options=bad", "direct"),
        ):
            with self.assertRaises(SetupError):
                validate_endpoint(url, mode, "generic")

    def test_session_supabase_and_direct_neon_allowed(self):
        validate_endpoint("postgresql://app:p@aws-0.pooler.supabase.com:5432/app?sslmode=require", "session", "supabase")
        validate_endpoint("postgresql://app:p@ep-demo.neon.tech/app?sslmode=verify-full", "direct", "neon")

    def test_retained_backend_and_nested_xact_lock(self):
        cur, other = Mock(), Mock()
        cur.fetchone.side_effect = [(123, True), (123, True), (123, True), (123, True), (True,)]
        other.fetchone.return_value = (False,)
        lock_probe(cur, other)
        sql = [call.args[0] for call in cur.execute.call_args_list]
        self.assertEqual(sql.count("COMMIT"), 3)
        self.assertTrue(any("pg_advisory_unlock" in q for q in sql))

    def test_transport_loss_or_changed_pid_refused_and_unlock_attempted(self):
        for nested in ((124, True), (123, False)):
            cur, other = Mock(), Mock()
            cur.fetchone.side_effect = [(123, True), nested, (True,)]
            other.fetchone.return_value = (False,)
            with self.assertRaises(SetupError):
                lock_probe(cur, other)
            self.assertIn("pg_advisory_unlock", cur.execute.call_args.args[0])

    def test_competing_connection_cannot_own_same_lock(self):
        cur, other = Mock(), Mock()
        cur.fetchone.side_effect = [(123, True), (123, True), (True,)]
        other.fetchone.return_value = (True,)
        with self.assertRaises(SetupError) as raised:
            lock_probe(cur, other)
        self.assertEqual(raised.exception.code, "session_not_retained")

    def test_provider_errors_never_leak_dsn_signed_url_or_secret(self):
        def fail():
            raise RuntimeError("postgresql://user:SENTINEL@db/?signature=SENTINEL")
        report = probe("database", fail)
        self.assertEqual(report["status"], "failed")
        self.assertNotIn("SENTINEL", str(report))

    def test_partial_connection_setup_closes_previously_open_session(self):
        first = Mock()
        values = {"DATABASE_URL": "postgresql://app:p@db.test/app?sslmode=require", "DATABASE_MAINTENANCE_URL": "postgresql://owner:p@db.test/app?sslmode=require"}
        answers = {"database_connection_mode": "direct", "maintenance_connection_mode": "direct", "database_provider": "generic"}
        from config.cloud_database import DatabaseConfigurationError
        # Connections now come from the shared validated builder (connect_database),
        # which wraps driver errors in a secret-free DatabaseConfigurationError.
        with patch("config.cloud_database.probes.probe_session_transport"),                 patch("config.cloud_database.connection.psycopg2.connect",
                      side_effect=[first, OSError("connect failed")]),                 self.assertRaises(DatabaseConfigurationError):
            database_probe(values, answers)
        first.close.assert_called_once()

    def test_every_help_path_works_without_django(self):
        for arguments in (["--help"], ["wizard", "--help"], ["init-from-current-environment", "--help"]):
            result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/init-cloud-environment.py"), *arguments], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("django", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
