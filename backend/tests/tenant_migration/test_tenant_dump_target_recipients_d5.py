"""D5 after P1b (#111 Q7): one-shot recipients prove possession; the target keeps no custody."""

import pytest

from apps.backup.models import BackupArchive
from apps.tenant_migration import tenant_dump_target
from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS


def test_activation_readiness_is_encryption_readiness_only(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tenant_dump_target, "run_target_encryption_readiness",
        lambda makerspace_id: calls.append(makerspace_id) or "ready",
    )

    assert tenant_dump_target.assert_target_d5_activation_ready(42) == "ready"
    assert calls == [42]


def test_no_recipient_reconstruction_step_remains():
    assert not hasattr(tenant_dump_target, "reconstruct_target_recipient_custody")


def test_no_archive_recipient_model_travels_in_a_tenant_dump():
    assert not any("ArchiveRecipient" in label for label in PROJECTED_MODEL_LABELS)
    assert not hasattr(__import__("apps.backup.models", fromlist=["x"]), "MakerspaceArchiveRecipient")
    assert BackupArchive._meta.get_field("makerspace")


@pytest.mark.parametrize("helper", ["decrypt_target_recipient_challenge"])
def test_the_recipient_challenge_helper_is_gone(helper):
    from apps.tenant_migration import tenant_dump_target_deks, tenant_dump_target_protocol

    assert not hasattr(tenant_dump_target_deks, helper)
    assert not hasattr(tenant_dump_target_protocol, "CHALLENGE_PROTOCOL")
