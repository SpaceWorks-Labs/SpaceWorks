"""Hidden lifecycle preserves the migration handoff and HTTP authority boundaries."""

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError

from apps.makerspaces import lifecycle
from apps.makerspaces.models import Makerspace
from apps.tenant_migration import cutover
from apps.tenant_migration.models import MigratedOutHandoff, MigrationReceipt, SourceMigrationGate
from tests.governance.test_gov_lifecycle import platform
from tests.tenant_migration.protocol_helpers import source_pairing, signed_envelope
from tests.tenant_migration.test_cutover import _quiesce_source

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def encryption_key(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode("ascii")


@pytest.fixture(autouse=True)
def activated_cutover(transactional_db):
    """conftest skips its activated-deployment fixture for any file named *migration*,
    and these are tenant-migration (not schema-migration) tests that purge a space."""
    from django.utils import timezone
    from apps.integrations.models_cutover import NotificationCutover
    now = timezone.now()
    NotificationCutover.objects.update_or_create(pk=1, defaults={
        "route": "canonical", "sending_enabled": True, "barrier_at": now,
        "copied_at": now, "reconciled_at": now, "activated_at": now})


def hidden_source(actor):
    source = Makerspace.objects.create(name="Hidden migration source", slug="gov-migration-source")
    pairing, target, private = source_pairing(actor, source)
    source.refresh_from_db()
    return source, pairing, target, private


def test_hidden_migrated_out_unarchive_refused_but_signed_abort_reopens():
    actor = platform()
    source, pairing, target, private = hidden_source(actor)
    gate = _quiesce_source(source, actor)
    cutover.retire_source(pairing=pairing, makerspace=source, actor=actor)
    source.refresh_from_db()
    assert source.archived_at
    with pytest.raises(ValidationError, match="signed abort receipt"):
        lifecycle.unarchive(source, actor)
    envelope = signed_envelope(pairing, MigrationReceipt.Operation.TARGET_ABORT, target, private)
    cutover.reopen_source(pairing=pairing, makerspace=source, receipt_envelope=envelope, actor=actor)
    source.refresh_from_db()
    gate.refresh_from_db()
    assert source.archived_at is None
    assert gate.state == SourceMigrationGate.State.OPEN


@pytest.mark.parametrize("managed", [False, True])
def test_hidden_migrated_out_purge_keeps_source_quiescence_exemption(managed, settings, monkeypatch):
    settings.MANAGED_POSTGRES = managed
    actor = platform()
    source, pairing, target, private = hidden_source(actor)
    gate = _quiesce_source(source, actor)
    cutover.retire_source(pairing=pairing, makerspace=source, actor=actor)
    source.refresh_from_db()
    source_id = source.pk
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", lambda keys: None)
    monkeypatch.setattr(lifecycle, "_delete_public_image_keys", lambda keys: None)
    lifecycle.purge(source, actor)
    assert not Makerspace.objects.filter(pk=source_id).exists()
    assert not SourceMigrationGate.objects.filter(pk=gate.pk).exists()


def test_hidden_failed_cutover_rolls_back_gate_archive_and_receipt(monkeypatch):
    actor = platform()
    source, pairing, target, private = hidden_source(actor)
    gate = _quiesce_source(source, actor)
    def fail_handoff(**kwargs):
        raise RuntimeError("injected hidden cutover failure")
    monkeypatch.setattr(MigratedOutHandoff.objects, "create", fail_handoff)
    with pytest.raises(RuntimeError, match="injected"):
        cutover.retire_source(pairing=pairing, makerspace=source, actor=actor)
    source.refresh_from_db()
    gate.refresh_from_db()
    assert source.archived_at is None
    assert gate.state == SourceMigrationGate.State.QUIESCED
    assert not MigrationReceipt.objects.filter(pairing=pairing).exists()
    assert not MigratedOutHandoff.objects.filter(pairing=pairing).exists()
