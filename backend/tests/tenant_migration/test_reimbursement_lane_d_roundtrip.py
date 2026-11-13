"""Lane D: capture -> derive -> restore into a fresh database for travel support rows.

The derived database image must carry every stage-form, reimbursement and payout-ledger
row with its primary key, apply the declared import resets, drop work rows and cleanup
locators, and keep payee bank data and decision summaries as the exact source
ciphertext (Lane D never re-encrypts and carries no plaintext).
"""
import hashlib
import shutil

import pytest
from django.db import connection, connections

from apps.backup import storage as backup_storage
from apps.backup.projection_databases import restore_dump, temporary_database
from apps.tenant_migration import tenant_dump_derivation
from apps.tenant_migration.tenant_dump_capture import capture_tenant_dump_source, request_tenant_dump_capture
from apps.tenant_migration.tenant_dump_derivation import derive_tenant_dump
from tests.encryption.conftest import enabled_encryption
from tests.event_reimbursements.conftest import make_world  # noqa: F401 - fixture
from tests.event_reimbursements.helpers import submitted
from tests.tenant_migration.object_helpers import memory_objects  # noqa: F401 - fixture
from tests.tenant_migration.tenant_dump_d3_helpers import manager, recipient
from tests.tenant_migration.test_reimbursement_roundtrip import (
    PAYEE_SECRET, RECEIPT_BYTES, _payout, _stage_file,
)

pytestmark = pytest.mark.django_db(transaction=True)

TABLES = {
    "event_reimbursements_reimbursementclaim": ("id", "uuid", "state", "member_id", "award_id", "current_decision_id"),
    "event_reimbursements_grantaward": ("id", "uuid", "amount_minor", "state", "request_id"),
    "event_reimbursements_claimdecision": ("id", "uuid", "approved_total_minor", "core_obligation_id", "claim_id"),
    "event_reimbursements_claimline": ("id", "line_uuid", "finance_asset_id", "receipt_hash"),
    "payments_eventpayoutobligation": ("id", "source_uuid", "approved_minor", "state", "current_revision_id"),
    "payments_eventpayoutentry": ("id", "amount_minor", "obligation_id", "payee_revision_id"),
    "payments_eventpayeerevision": ("id", "obligation_id", "details", "state"),
    "payments_eventpayoutobligationrevision": ("id", "obligation_id", "decision_summary"),
    "payments_financeattachment": ("id", "object_key", "sha256", "state"),
    "events_stageformasset": ("id", "object_key", "sha256", "state"),
    "events_stageformresponse": ("id", "answers_snapshot", "state", "current_submitted_revision_id"),
    "events_stageformresponserevision": ("id", "answers_snapshot"),
}
EMPTY_ON_TARGET = ("events_stagefilecleanup", "payments_financeobjectcleanup", "payments_eventpayoutcommandreceipt")


def _rows(cursor, table, columns, makerspace_id=None):
    cursor.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")
    return cursor.fetchall()


def test_lane_d_dump_restores_stage_reimbursement_and_payout_rows(
    make_world, monkeypatch, memory_objects, settings, tmp_path, allow_projection_databases,
):
    with enabled_encryption():
        world = make_world()
        settings.EVENT_PAYOUT_TENANT_POLICIES = {str(world.space.pk): {"templates": [("IN", "bank_transfer", "in_bank", 1)]}}
        claim, receipt, line_id = submitted(world, monkeypatch)
        _payout(world, claim, line_id)
        stage_asset, stage_bytes = _stage_file(world, monkeypatch)
        world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"notifications"})
        world.space.save(update_fields=["enabled_modules"])
        actor = manager(world.space)
        settings.TENANT_DUMP_STAGING_DIR = str(tmp_path / "staging")
        objects = {receipt.object_key: RECEIPT_BYTES, stage_asset.object_key: stage_bytes}

        def download(_bucket, key, destination, *, versioned):
            data = objects[key]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "version_id": "v1",
                    "content_type": "application/octet-stream"}
        monkeypatch.setattr(backup_storage, "download_object", download)
        monkeypatch.setattr(backup_storage, "assert_object_absent", lambda bucket, key: None)
        with connection.cursor() as cursor:
            source = {table: _rows(cursor, table, columns) for table, columns in TABLES.items()}
        assert all(source[table] for table in TABLES), "every travelling table needs a source row"

        # Seal with stand-ins (no age binary / helper process); keep the inner image.
        derived = tmp_path / "derived.dump"

        def seal_deks(source_rows, retained_rows, recipients, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"sealed-deks")
            return {"path": "keys/tenant-deks.age", "size": destination.stat().st_size,
                    "sha256": hashlib.sha256(b"sealed-deks").hexdigest()}

        def seal_outer(bundle, destination, recipients, **facts):
            shutil.copyfile(bundle / "database.dump", derived)
            destination.write_bytes(b"sealed-outer")
        monkeypatch.setattr(tenant_dump_derivation, "seal_tenant_deks", seal_deks)
        monkeypatch.setattr(tenant_dump_derivation, "seal_outer_bundle", seal_outer)

        # The scratch database's `manage.py migrate` is a subprocess: it reads keys from the
        # environment, not from this test's settings overrides.
        from cryptography.fernet import Fernet
        for name in ("PII_MASTER_KEY", "PII_SEARCH_HASH_KEY", "ACCOUNT_PII_MASTER_KEY"):
            monkeypatch.setenv(name, getattr(settings, name, "") or Fernet.generate_key().decode())
        settings.BACKUP_AGE_RECIPIENT = recipient(world.space, 72)
        capture = request_tenant_dump_capture(
            actor, world.space, recipients=[recipient(world.space, 71)]
        )
        capture_tenant_dump_source(capture.pk, sleep=lambda _seconds: None,
                                   storage_modes={"private": "versioned", "public_image": "versioned"})
        derive_tenant_dump(capture.pk)
        assert PAYEE_SECRET.encode() not in derived.read_bytes()

        with temporary_database("lane_d_reimb") as (using, database_name):
            restore_dump(derived, database_name)
            with connections[using].cursor() as cursor:
                restored = {table: _rows(cursor, table, columns) for table, columns in TABLES.items()}
                for table in EMPTY_ON_TARGET:
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    assert cursor.fetchone()[0] == 0, table
                cursor.execute("SELECT enabled, imported_paused FROM event_reimbursements_reimbursementprogramme")
                assert cursor.fetchall() == [(False, True)]
                cursor.execute("SELECT imported_paused FROM events_stageformassignment")
                assert {row[0] for row in cursor.fetchall()} == {True}
                cursor.execute("SELECT lease_token, staging_version_id, final_version_id FROM payments_financeattachment")
                assert set(cursor.fetchall()) == {(None, "", "")}
            connections[using].close()

        # Same primary keys and the same values, byte for byte for ciphertext columns.
        assert restored == source
        for (_pk, _obligation, details, _state) in restored["payments_eventpayeerevision"]:
            assert details.startswith("pii:gcm:v1:") and PAYEE_SECRET not in details
        for (_pk, _obligation, summary) in restored["payments_eventpayoutobligationrevision"]:
            assert summary.startswith("pii:gcm:v1:")
