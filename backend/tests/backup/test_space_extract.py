"""#144: one space from a host-decrypted whole-platform backup becomes a restore point."""

import json

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.audit.models import AuditLog
from apps.backup import space_restore_runner as runner, space_restore_services as services
from apps.backup.archive_objects import capture_objects
from apps.backup.archive_payload import _storage_modes, _tenant_payload
from apps.backup.space_extract import extract_space_restore_point
from apps.backup.space_restore_plan import SpaceRestoreError
from apps.hardware_requests.models import HardwareRequest
from tests.backup.space_restore_helpers import make_user, put_public, seed_space
from tests.data_export.portable_helpers import make_space
from tests.backup.test_space_restore_flow import _superadmin, restore_keys  # noqa: F401
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


def _decrypted_platform_archive(root, space, *, covered=None, **overrides):
    """What the operator gets after `age --decrypt` of a whole-platform archive."""
    from apps.backup.cloud_database_tools import configuration_spec
    from apps.backup.postgres_client import run_client

    root.mkdir(parents=True)
    run_client("pg_dump", ["--format=custom", "--no-owner", "--no-acl", f"--file={root / 'database.dump'}"],
               spec=configuration_spec(settings.DATABASES["default"]))
    keys = _tenant_payload(space.pk, root / "_probe")
    objects = capture_objects(root / "objects", keys, _storage_modes())
    manifest = {"format": "spaceworks-phase5a-v3", "archive_id": "deploy-1", "scope": "deployment",
                "covered_makerspace_ids": covered if covered is not None else [space.pk], "partial": False,
                "snapshot_at": "2026-10-30T00:00:00+00:00", "storage": {"objects": objects}, **overrides}
    (root / "manifest.json").write_text(json.dumps(manifest, default=str), encoding="utf-8")
    import shutil
    shutil.rmtree(root / "_probe")
    return root


def test_extracted_point_restores_through_the_ordinary_flow(restore_keys, tmp_path, allow_projection_databases):  # noqa: F811
    with enabled_encryption():
        root = _superadmin()
        member = make_user("extract-member")
        space, request = seed_space("extract-space", member)
        source = _decrypted_platform_archive(tmp_path / "decrypted", space)
        HardwareRequest.objects.filter(pk=request.pk).update(status="rejected")
        put_public(space.logo_key, b"changed after the platform backup")

        point = extract_space_restore_point(root, source, space)
        assert point.trigger == "extracted" and point.status == "available" and point.format == "tenant_slice_v2"
        assert AuditLog.objects.filter(makerspace=space, action="backup.space_restore_point_extracted").exists()

        op = services.request_restore(root, space, point)
        assert runner.run_preview(op.pk).stage == "preview_ready"
        services.confirm_restore(root, type(op).objects.get(pk=op.pk), space.slug)
        done = runner.run_apply(op.pk)
        assert done.stage == "completed", (done.error_code, done.error_detail)
        assert HardwareRequest.objects.get(pk=request.pk).status != "rejected"
        assert done.report["objects_restored"] == 1


@pytest.mark.parametrize("problem", ["not_covered", "partial", "wrong_scope", "identity_left", "link", "missing_dump"])
def test_unsafe_or_wrong_input_is_refused_before_anything_is_written(restore_keys, tmp_path, problem):  # noqa: F811
    from apps.backup.models import BackupArchive
    root = _superadmin()
    space = make_space("extract-refuse")
    source = tmp_path / "decrypted"
    source.mkdir()
    (source / "database.dump").write_bytes(b"not used")
    manifest = {"format": "spaceworks-phase5a-v3", "scope": "deployment", "covered_makerspace_ids": [space.pk]}
    if problem == "not_covered":
        manifest["covered_makerspace_ids"] = [space.pk + 1000]
    elif problem == "partial":
        manifest["partial"] = True
    elif problem == "wrong_scope":
        manifest["scope"] = "makerspace"
    elif problem == "identity_left":
        (source / "platform.key").write_text("# created\nAGE-SECRET-KEY-1QQQQ\n")
    elif problem == "link":
        (source / "evil").symlink_to(tmp_path)
    elif problem == "missing_dump":
        (source / "database.dump").unlink()
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(SpaceRestoreError):
        extract_space_restore_point(root, source, space)
    assert not BackupArchive.objects.exists()


def test_only_a_platform_superadmin_may_extract(restore_keys, tmp_path):  # noqa: F811
    space = make_space("extract-staff")
    with pytest.raises(SpaceRestoreError, match="superadmin"):
        extract_space_restore_point(make_user("not-root"), tmp_path, space)
    with pytest.raises(CommandError, match="Unknown"):
        call_command("extract_space_restore_point", username="nobody", source=str(tmp_path), makerspace=space.slug)
