"""Real recipient custody survives archival and is torn down only by tenant purge."""

import pytest as _legacy_pytest

_legacy_pytest.skip('Not in release 0.12.0: apps.backup.activation, apps.backup.custody, apps.backup.models.ArchiveCustodyAlarmDelivery, apps.backup.models.ArchiveRecipientReservation (+8 more)', allow_module_level=True)

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.backup.activation import set_superadmin_access
from apps.backup.custody import with_makerspace_custody_lock
from apps.backup.models import (
    ArchiveCustodyAlarmDelivery, ArchiveRecipientReservation, B1ActivationState,
    BackupArchive, BackupArtifactComponent, BackupArtifactLedger, BackupComponentRecipient,
    MakerspaceArchiveCustodyState, MakerspaceArchiveRecipient,
    MakerspaceTenantExitCustodyState, TenantExitCustodyAlarmDelivery,
)
from apps.backup.recipient_selection import selection_for
from apps.backup.recipients import encode_unpadded_base64url, enroll_recipient, nonce_digest, verify_recipient
from apps.backup.recipients_bech32 import convert_bits, encode
from apps.encryption.models import MakerspaceEncryptionKey
from apps.encryption.services import get_or_create_active_dek
from apps.makerspaces import lifecycle
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption
from tests.governance.test_gov_lifecycle import platform

pytestmark = pytest.mark.django_db(transaction=True)


def verified_recipient(space, number):
    # Canonical 32-byte native age public keys and the real challenge verifier;
    # no mocked recipient population or custody admission.
    public = encode("age", convert_bits(bytes([number]) * 32, 8, 5, pad=True))
    recipient = enroll_recipient(makerspace=space, public_recipient=public, label=f"Custodian {number}")
    nonce = bytes([number + 10]) * 32
    recipient.challenge_nonce_digest = nonce_digest(nonce)
    recipient.challenge_issued_at = timezone.now()
    recipient.save(update_fields=("challenge_nonce_digest", "challenge_issued_at"))
    return verify_recipient(recipient_id=recipient.pk, makerspace_id=space.pk,
                            submitted_nonce=encode_unpadded_base64url(nonce))


def retained_artifact(space, recipients):
    archive = BackupArchive.objects.create(scope="makerspace", makerspace=space,
        superadmin_access_at_decision=False, object_key="retained/gov-encrypted-backup",
        age_encrypted=True, status="available", expires_at=timezone.now() + timedelta(days=30))
    artifact_id = uuid.uuid4()
    ledger = BackupArtifactLedger.objects.create(artifact_id=artifact_id, capture_id=uuid.uuid4(),
        archive=archive, archive_uuid_snapshot=archive.pk, outer_sha256="a" * 64,
        outer_manifest_sha256="b" * 64, format="spaceworks.compound.v1", outer_manifest={},
        frozen_promotion_snapshot={}, expected_size_bytes=42,
        staging_locator="retained/gov-stage", final_locator="retained/gov-final")
    component = BackupArtifactComponent.objects.create(artifact=ledger, component_id=uuid.uuid4(),
        kind="slice", makerspace_id_snapshot=space.pk, ciphertext_path="slices/tenant.age",
        ciphertext_sha256="c" * 64, size_bytes=42)
    for recipient in recipients:
        BackupComponentRecipient.objects.create(component=component, fingerprint=recipient.fingerprint)
    return archive, ledger, component


@pytest.mark.parametrize("activation_state", ["off_pending", "off_effective"])
@pytest.mark.parametrize("managed", [False, True])
def test_hidden_archive_preserves_custody_and_purge_retains_only_durable_artifacts(
    activation_state, managed, settings, monkeypatch,
):
    settings.MANAGED_POSTGRES = managed
    actor = platform()
    space = Makerspace.objects.create(name="Governance custody", slug="governance-custody")
    if "backup" not in space.enabled_modules:
        space.enabled_modules = [*space.enabled_modules, "backup"]
        space.save(update_fields=("enabled_modules",))
    recipients = [verified_recipient(space, index) for index in (1, 2)]
    with with_makerspace_custody_lock(space.pk) as custody:
        set_superadmin_access(custody, enabled=False, actor=actor)
    archive, ledger, component = retained_artifact(space, recipients)
    if activation_state == "off_effective":
        B1ActivationState.objects.filter(makerspace=space).update(state=activation_state,
            effective_artifact_id=ledger.pk, effective_at=timezone.now())
    before_activation = B1ActivationState.objects.values().get(makerspace=space)
    before_recipients = list(MakerspaceArchiveRecipient.objects.filter(makerspace=space).order_by("pk").values())
    before_custody = MakerspaceArchiveCustodyState.objects.values().get(makerspace=space)
    expected = [{"label": recipient.label, "public_recipient": recipient.public_recipient} for recipient in recipients]
    assert selection_for(archive) == expected  # platform identity is never selected
    lifecycle.archive(space, actor)
    space.refresh_from_db()
    lifecycle.unarchive(space, actor)
    assert B1ActivationState.objects.values().get(makerspace=space) == before_activation
    assert list(MakerspaceArchiveRecipient.objects.filter(makerspace=space).order_by("pk").values()) == before_recipients
    assert MakerspaceArchiveCustodyState.objects.values().get(makerspace=space) == before_custody
    assert selection_for(archive) == expected
    with enabled_encryption():
        get_or_create_active_dek(space.pk)
    assert MakerspaceEncryptionKey.objects.filter(makerspace=space).exists()
    # Verifying the first recipient already emits a revision-1 exit-custody alarm.
    # Reuse that durable intent instead of colliding with its delivery identity.
    TenantExitCustodyAlarmDelivery.objects.get_or_create(makerspace=space, alarm_revision=1,
        cycle=0, channel="operator_email", recipient_ref=actor.pk, defaults={"recipient_user": actor})
    ArchiveCustodyAlarmDelivery.objects.get_or_create(makerspace=space, alarm_revision=1,
        cycle=0, channel="operator_email", recipient_ref=actor.pk, defaults={"recipient_user": actor})
    assert TenantExitCustodyAlarmDelivery.objects.filter(makerspace=space).exists()
    assert ArchiveCustodyAlarmDelivery.objects.filter(makerspace=space).exists()
    space = lifecycle.archive(space, actor)
    space_id = space.pk
    removed_private_keys, removed_public_keys = [], []
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", removed_private_keys.extend)
    monkeypatch.setattr(lifecycle, "_delete_public_image_keys", removed_public_keys.extend)
    lifecycle.purge(space, actor)
    assert not Makerspace.objects.filter(pk=space_id).exists()
    for model in (MakerspaceArchiveRecipient, MakerspaceArchiveCustodyState, B1ActivationState,
                  MakerspaceEncryptionKey, MakerspaceTenantExitCustodyState,
                  ArchiveCustodyAlarmDelivery, TenantExitCustodyAlarmDelivery):
        assert not model.objects.filter(makerspace_id=space_id).exists()
    assert ArchiveRecipientReservation.objects.filter(makerspace_id_snapshot=space_id).count() == 2
    archive.refresh_from_db()
    assert archive.makerspace_id is None and archive.superadmin_access_at_decision is False
    assert archive.age_encrypted and archive.object_key == "retained/gov-encrypted-backup"
    assert BackupArtifactLedger.objects.filter(pk=ledger.pk).exists()
    assert BackupArtifactComponent.objects.get(pk=component.pk).makerspace_id_snapshot == space_id
    assert BackupComponentRecipient.objects.filter(component=component).count() == 2
    assert archive.object_key not in removed_private_keys + removed_public_keys
