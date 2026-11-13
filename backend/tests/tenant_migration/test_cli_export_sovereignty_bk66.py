"""BK-66: the command-line tenant-archive export encrypts to the PLATFORM key, so it must
refuse a makerspace that turned superadmin access off -- the gate the HTTP path has."""

import pytest
from django.core.management import CommandError, call_command

from apps.makerspaces.models import Makerspace
from apps.tenant_migration import archive_envelope

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skip(reason="decision 110 (superadmin always on; Makerspace.superadmin_access_enabled and the platform-custody gate removed)"),
]


def _space(slug, *, access):
    space = Makerspace.objects.create(name=slug, slug=slug)
    space.superadmin_access_enabled = access
    space.save(update_fields=["superadmin_access_enabled"])
    return space


def test_builder_refuses_platform_key_when_superadmin_access_is_off(settings, tmp_path):
    settings.BACKUP_AGE_RECIPIENT = "age1recipient"
    space = _space("bk66-off", access=False)
    output = tmp_path / "out.tar.age"

    with pytest.raises(archive_envelope.MigrationArchiveError, match="turned superadmin access off"):
        archive_envelope.build_tenant_migration_archive(space, output)

    assert not output.exists()


def test_builder_reads_the_switch_from_the_database_not_the_instance(settings, tmp_path):
    settings.BACKUP_AGE_RECIPIENT = "age1recipient"
    space = _space("bk66-stale", access=True)
    Makerspace.objects.filter(pk=space.pk).update(superadmin_access_enabled=False)
    assert space.superadmin_access_enabled is True  # stale caller copy

    with pytest.raises(archive_envelope.MigrationArchiveError, match="turned superadmin access off"):
        archive_envelope.build_tenant_migration_archive(space, tmp_path / "out.tar.age")


def test_gate_admits_a_space_with_superadmin_access_on():
    space = _space("bk66-on", access=True)
    archive_envelope._require_platform_custody_allowed(space)


def test_target_keyed_export_is_not_subject_to_the_platform_gate(monkeypatch, settings, tmp_path):
    """The HTTP job path passes the target's recipient and is gated at the view instead."""
    space = _space("bk66-target", access=False)
    seen = []
    monkeypatch.setattr(archive_envelope, "_require_platform_custody_allowed", seen.append)
    monkeypatch.setattr(archive_envelope, "_current_approval", lambda _space: object())
    monkeypatch.setattr(archive_envelope, "_require_binary", lambda _c: (_ for _ in ()).throw(RuntimeError("stop")))

    with pytest.raises(archive_envelope.MigrationArchiveError, match="stop"):
        archive_envelope.build_tenant_migration_archive(
            space, tmp_path / "out.tar.age", recipient="age1target",
        )
    assert seen == []


def test_command_refuses_with_a_clear_error(settings, tmp_path):
    settings.BACKUP_AGE_RECIPIENT = "age1recipient"
    space = _space("bk66-cli", access=False)

    with pytest.raises(CommandError, match="turned superadmin access off"):
        call_command(
            "export_tenant_migration_archive",
            makerspace=space.slug, output=str(tmp_path / "cli.tar.age"),
        )
