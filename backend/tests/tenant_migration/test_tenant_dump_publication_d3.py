import pytest

from apps.backup.digests import sha256_file
from apps.data_export.models import OMITTED_MODELS
from apps.tenant_migration.models import TenantDumpCapture
from apps.tenant_migration.tenant_dump_capture import request_tenant_dump_capture
from apps.tenant_migration.tenant_dump_cleanup import (
    cleanup_refused_tenant_dump_artifacts,
)
from apps.tenant_migration.tenant_dump_errors import TenantDumpCustodyError
from apps.tenant_migration.tenant_dump_envelope import (
    build_outer_manifest,
    write_outer_artifact,
)
from apps.tenant_migration.tenant_dump_lineage import FORMAT
from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
from apps.tenant_migration.tenant_dump_publication import register_unpublished_artifact
from apps.tenant_migration.tenant_dump_recipients import recipient_sets
from apps.tenant_migration.tenant_dump_types import ModelDisposition
from tests.tenant_migration.tenant_dump_d3_helpers import (
    makerspace,
    manager,
    recipient,
)


pytestmark = pytest.mark.django_db


def _pending_capture(space, actor, seeds=(20,)):
    capture = request_tenant_dump_capture(
        actor, space, recipients=[recipient(space, seed) for seed in seeds]
    )
    capture.status = TenantDumpCapture.Status.PENDING_PUBLICATION
    capture.unpublished_object_key = f"tenant-dumps/unpublished/{capture.pk}.tar.age"
    capture.save(update_fields=("status", "unpublished_object_key", "updated_at"))
    return capture


def test_request_freezes_canonical_one_shot_recipients_and_audits_only_fingerprints():
    from apps.audit.models import AuditLog

    space = makerspace("d3-one-shot")
    actor = manager(space)
    keys = [recipient(space, 11), recipient(space, 10).upper()]
    capture = request_tenant_dump_capture(actor, space, recipients=keys)

    stored = capture.tenant_recipients
    assert [item["public_recipient"] for item in stored] == sorted(
        (key.lower() for key in keys), key=lambda value: next(
            item["fingerprint"] for item in stored if item["public_recipient"] == value
        )
    )
    audit = AuditLog.objects.get(action="tenant_migration.tenant_dump_requested")
    assert audit.meta["recipient_fingerprints"] == [item["fingerprint"] for item in stored]
    assert all(key.lower() not in str(audit.meta) for key in keys)


@pytest.mark.parametrize("bad", [[], ["not-a-key"], "dup", "platform"])
def test_request_refuses_missing_invalid_duplicate_or_platform_recipients(bad, settings):
    space = makerspace(f"d3-bad-{len(str(bad))}-{bad if isinstance(bad, str) else 'x'}")
    actor = manager(space)
    settings.BACKUP_AGE_RECIPIENT = recipient(space, 99)
    keys = {
        "dup": [recipient(space, 5), recipient(space, 5)],
        "platform": [recipient(space, 99)],
    }.get(bad, bad) if isinstance(bad, str) else bad
    with pytest.raises(TenantDumpCustodyError):
        request_tenant_dump_capture(actor, space, recipients=keys)
    assert not TenantDumpCapture.objects.filter(makerspace=space).exists()


def test_outer_envelope_always_adds_the_platform_key_but_deks_stay_tenant_only(settings):
    space = makerspace("d3-envelope-sets")
    actor = manager(space)
    settings.BACKUP_AGE_RECIPIENT = recipient(space, 77)
    capture = _pending_capture(space, actor, seeds=(30, 31))

    sets = recipient_sets(capture)

    tenant = tuple(item["public_recipient"] for item in capture.tenant_recipients)
    assert sets.tenant_dek_recipients == tenant
    assert sets.outer_recipients == (*tenant, recipient(space, 77))


def test_failed_unpublished_delete_retains_a_durable_retry_key(monkeypatch):
    space = makerspace("d3-delete-retry")
    actor = manager(space)
    capture = _pending_capture(space, actor)
    capture.status = TenantDumpCapture.Status.REFUSED
    capture.save(update_fields=("status", "updated_at"))
    monkeypatch.setattr(
        "apps.tenant_migration.tenant_dump_cleanup.storage.delete_archive",
        lambda _key: False,
    )

    assert cleanup_refused_tenant_dump_artifacts() == 0
    capture.refresh_from_db()
    assert capture.unpublished_object_key.endswith(".tar.age")


def test_failed_artifact_registration_journals_an_undeletable_upload(
    monkeypatch, tmp_path
):
    space = makerspace("d3-register-retry")
    actor = manager(space)
    capture = _pending_capture(space, actor)
    capture.unpublished_object_key = ""
    capture.save(update_fields=("unpublished_object_key", "updated_at"))
    artifact = tmp_path / "sealed.tar.age"
    payload = tmp_path / "payload.age"
    payload.write_bytes(b"sealed")
    write_outer_artifact(
        payload,
        artifact,
        build_outer_manifest(
            format=FORMAT,
            version=1,
            artifact_id=capture.pk,
            capture_id=capture.pk,
            outer_recipient_fingerprints=["outer"],
            tenant_dek_recipient_fingerprints=["tenant"],
            encrypted_members=[{
                "path": "payload.age",
                "sha256": sha256_file(payload),
                "size": payload.stat().st_size,
            }],
            source_build={"source_hash": "a" * 64},
            postgres_major=16,
            compatibility={},
        ),
    )

    original_save = TenantDumpCapture.save
    failed_once = False

    def fail_first_registration(row, *args, **kwargs):
        nonlocal failed_once
        if row.unpublished_object_key and not failed_once:
            failed_once = True
            raise RuntimeError("registration failed")
        return original_save(row, *args, **kwargs)

    monkeypatch.setattr(TenantDumpCapture, "save", fail_first_registration)
    monkeypatch.setattr(
        "apps.tenant_migration.tenant_dump_publication.storage.upload_archive",
        lambda _key, _path: None,
    )
    monkeypatch.setattr(
        "apps.tenant_migration.tenant_dump_publication.storage.delete_archive",
        lambda _key: False,
    )

    with pytest.raises(RuntimeError, match="registration failed"):
        register_unpublished_artifact(capture.pk, artifact)

    capture.refresh_from_db()
    assert capture.status == TenantDumpCapture.Status.FAILED
    assert capture.refusal_code == "artifact_registration_failed"
    assert capture.unpublished_object_key.endswith(".tar.age")


def test_lane_d_operational_rows_are_drop_disposition():
    labels = {"tenant_migration.TenantDumpCapture"}
    assert labels <= set(OMITTED_MODELS)
    assert all(
        FIRST_PARTY_MODEL_RULES[label].disposition == ModelDisposition.DROP
        for label in labels
    )
