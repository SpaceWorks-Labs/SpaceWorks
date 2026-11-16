"""Local SQL predicate regression tests; actual PostgreSQL remains a Docker gate."""
from pathlib import Path
import sqlite3
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from apps.backup.managed.legacy_staging import assert_durable_staging, request_origin


class Cursor:
    def __init__(self, database):
        self.database = database
        self.result = None

    def execute(self, query, params=()):
        if not query.lstrip().startswith("SELECT"):
            raise AssertionError("Admission attempted a mutation")
        if "to_regclass" in query:
            name = params[0].removeprefix("public.")
            found = self.database.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]).fetchone()
            self.result = (name if found else None,)
        else:
            # Execute the actual production predicates, translating only driver
            # placeholders, schema qualification and PostgreSQL timestamp casts.
            query = query.replace("public.", "").replace("%s", "?").replace("::timestamptz", "").replace("::text", "")
            self.result = self.database.execute(query, params).fetchone()

    def fetchone(self):
        return self.result


class LegacyStagingTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")
        self.addCleanup(self.database.close)
        self.database.executescript("""
CREATE TABLE tenant_migration_tenantimportjob (status text, archive_path text, scrubbed_at text);
CREATE TABLE tenant_migration_tenantdumpcapture (id text, status text, created_at text);
CREATE TABLE backup_manageddeploymentstate (id integer, deployment_id text, database_uuid text);
CREATE TABLE audit_auditlog (action text,target_type text,target_id text,meta text);
CREATE TABLE backup_managedstagedobject (owner text,label text,available boolean,selected boolean,delete_requested_at text,deleted_at text,expires_at text);
INSERT INTO backup_manageddeploymentstate VALUES (1,'deployment','database');
""")
        self.patch = patch.dict(sys.modules, {"apps.backup.managed.admission": SimpleNamespace(ManagedAdmissionError=ValueError)})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def admit(self):
        assert_durable_staging(Cursor(self.database))

    def test_nonterminal_local_and_empty_imports_refuse_without_mutation(self):
        for path in ("/old-host/archive.age", "C:/old-host/archive.age", ""):
            self.database.execute("DELETE FROM tenant_migration_tenantimportjob")
            self.database.execute("INSERT INTO tenant_migration_tenantimportjob VALUES ('pending',?,NULL)", [path])
            with self.assertRaisesRegex(ValueError, "original host"):
                self.admit()
            self.assertEqual(self.database.execute("SELECT archive_path FROM tenant_migration_tenantimportjob").fetchone(), (path,))

    def test_new_durable_import_markers_are_admitted(self):
        for path in ("cloud-stage:11111111-2222-3333-4444-555555555555", "cloud-upload:11111111-2222-3333-4444-555555555555"):
            self.database.execute("INSERT INTO tenant_migration_tenantimportjob VALUES ('pending',?,NULL)", [path])
        self.admit()

    def test_terminal_scrubbed_or_empty_rows_are_admitted(self):
        self.database.executemany("INSERT INTO tenant_migration_tenantimportjob VALUES (?,?,?)", [
            ("failed", "/old-host/retired.age", "2026-10-17"), ("completed", "", None), ("abandoned", "", "2026-10-17")])
        self.admit()

    def test_unscrubbed_terminal_local_retention_requires_drain(self):
        self.database.execute("INSERT INTO tenant_migration_tenantimportjob VALUES ('failed','/old-host/retained.age',NULL)")
        with self.assertRaises(ValueError):
            self.admit()

    def test_pre_adoption_active_capture_requires_durable_payload(self):
        self.database.execute("INSERT INTO tenant_migration_tenantdumpcapture VALUES ('capture','captured','2026-10-17T00:00:00')")
        with self.assertRaises(ValueError):
            self.admit()
        self.database.execute("INSERT INTO backup_managedstagedobject VALUES ('capture','source',1,1,NULL,NULL,'2999-01-01')")
        self.admit()
        self.database.execute("UPDATE backup_managedstagedobject SET deleted_at='2026-10-18'")
        with self.assertRaises(ValueError):
            self.admit()

    def test_unbound_adoption_treats_active_capture_as_legacy(self):
        self.database.execute("DELETE FROM backup_manageddeploymentstate")
        self.database.execute("INSERT INTO tenant_migration_tenantdumpcapture VALUES ('capture','capturing','2026-10-19T00:00:00')")
        with self.assertRaises(ValueError):
            self.admit()

    def test_new_managed_capture_can_create_its_first_payload_and_terminal_history_is_inert(self):
        self.database.executemany("INSERT INTO tenant_migration_tenantdumpcapture VALUES (?,?,?)", [
            ("new", "capturing", "2026-10-19T00:00:00"), ("old", "published", "2026-10-17T00:00:00"),
            ("failed", "failed", "2026-10-17T00:00:00"), ("refused", "refused", "2026-10-17T00:00:00")])
        # Even future host clocks do not establish managed origin.
        with self.assertRaises(ValueError):
            self.admit()
        proof = {"staging_backend": "managed-object-v1", "staging_capture_id": "new",
                 "staging_deployment_id": "deployment", "staging_database_uuid": "database"}
        self.database.execute("INSERT INTO audit_auditlog VALUES (?,?,?,?)", [
            "tenant_migration.tenant_dump_requested", "tenant_migration.tenantdumpcapture", "new", json.dumps(proof)])
        self.admit()
        self.database.execute("UPDATE audit_auditlog SET meta=?", [json.dumps({**proof, "staging_database_uuid": "wrong-database"})])
        with self.assertRaises(ValueError):
            self.admit()
        self.database.execute("UPDATE audit_auditlog SET meta=?,target_id='other-capture'", [json.dumps(proof)])
        with self.assertRaises(ValueError):
            self.admit()

    def test_older_schema_without_job_tables_has_nothing_local_to_adopt(self):
        self.database.execute("DROP TABLE tenant_migration_tenantimportjob")
        self.database.execute("DROP TABLE tenant_migration_tenantdumpcapture")
        self.admit()

    def test_request_proof_uses_primary_binding_and_exact_capture(self):
        lookups = []
        def get(**values):
            lookups.append(values)
            return SimpleNamespace(deployment_id="deployment", database_uuid="database")
        model = SimpleNamespace(objects=SimpleNamespace(get=get))
        with patch.dict(sys.modules, {"apps.backup.managed.models": SimpleNamespace(ManagedDeploymentState=model)}):
            proof = request_origin(SimpleNamespace(pk="exact-capture"))
        self.assertEqual(lookups, [{"pk": 1}])
        self.assertEqual(proof, {"staging_backend": "managed-object-v1", "staging_capture_id": "exact-capture",
            "staging_deployment_id": "deployment", "staging_database_uuid": "database"})


if __name__ == "__main__":
    unittest.main()
