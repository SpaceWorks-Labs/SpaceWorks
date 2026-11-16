"""Restore drills (BK-10/BK-91, #128 C-22): isolated DB, throwaway identity, nothing live touched."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.db import connections
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.backup import restore_drill, restore_drill_checks
from apps.backup.models import BackupArchive, PlatformBackupSettings, RestoreDrillReport
from tests.backup.space_restore_helpers import make_user, seed_space
from tests.backup.test_space_restore_flow import _backup, _superadmin, restore_keys  # noqa: F401
from tests.backup.test_compound_archive_e3 import allow_projection_databases  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _encryption():
    from tests.encryption.conftest import enabled_encryption
    with enabled_encryption():
        yield


def test_a_drill_rebuilds_the_archive_in_an_isolated_database_and_leaves_nothing(restore_keys, monkeypatch,
                                                                              allow_projection_databases):
    root = _superadmin()
    space, _request = seed_space("drill-space", make_user("drill-member"))
    archive = _backup(space, root)
    live_identity = Path(restore_keys.TENANT_MIGRATION_AGE_IDENTITY_FILE).read_text()
    live_name = connections["default"].settings_dict["NAME"]
    seen = {}
    real_reconstruct, real_temp = restore_drill_checks.reconstruct, restore_drill_checks.temporary_database

    def spy_temp(role):
        context = real_temp(role)
        alias, name = context.__enter__()
        seen.update(alias=alias, name=name)

        class Wrapped:
            def __enter__(self):
                return alias, name

            def __exit__(self, *exc):
                return context.__exit__(*exc)
        return Wrapped()

    def spy_reconstruct(space_archive, workdir):
        seen["workdir"] = Path(workdir)
        from django.conf import settings
        seen["identity_during"] = settings.TENANT_MIGRATION_AGE_IDENTITY_FILE
        result = real_reconstruct(space_archive, workdir)
        seen["files"] = {path: path.read_bytes() for path in Path(workdir).rglob("*") if path.is_file()}
        return result

    monkeypatch.setattr(restore_drill_checks, "temporary_database", spy_temp)
    monkeypatch.setattr(restore_drill_checks, "reconstruct", spy_reconstruct)
    monkeypatch.setattr("apps.backup.storage.upload_archive", lambda *a, **k: pytest.fail("a drill never uploads"))
    report = restore_drill.run_drill(archive)
    assert report.outcome == "passed", (report.error_code, report.error_detail)
    assert report.checks["row_total"] > 0 and report.checks["database_isolated"] is True
    assert seen["alias"] != "default" and seen["name"] != live_name
    assert seen["identity_during"] != restore_keys.TENANT_MIGRATION_AGE_IDENTITY_FILE
    assert all(live_identity.strip().encode() not in content for content in seen["files"].values())
    assert not seen["workdir"].exists()  # the throwaway identity and every decrypted byte are gone
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [seen["name"]])
        assert cursor.fetchone() is None
    assert AuditLog.objects.filter(action="backup.drill_completed", makerspace=space).exists()
    archive.refresh_from_db()
    assert archive.status == BackupArchive.Status.AVAILABLE


def test_a_failed_drill_is_reported_and_tells_the_superadmin(restore_keys, monkeypatch):
    root = _superadmin()
    space, _request = seed_space("drill-fail", make_user("drill-fail-member"))
    archive = _backup(space, root)
    BackupArchive.objects.filter(pk=archive.pk).update(archive_sha256="0" * 64)
    archive.refresh_from_db()
    sent = []
    monkeypatch.setattr("apps.backup.operator_notice.notify_superadmins",
                        lambda subject, text, *, event: sent.append(event) or 1)
    report = restore_drill.run_drill(archive)
    assert (report.outcome, report.error_code) == ("failed", "archive_digest_mismatch")
    assert sent == ["backup_drill_failed"]
    assert AuditLog.objects.filter(action="backup.drill_failed").exists()


def test_the_due_archive_follows_the_interval_and_zero_turns_drills_off(restore_keys):
    root = _superadmin()
    space, _request = seed_space("drill-due", make_user("drill-due-member"))
    archive = _backup(space, root)
    assert restore_drill.due_archive().pk == archive.pk
    RestoreDrillReport.objects.create(makerspace=space, makerspace_id_snapshot=space.pk, archive=archive,
                                      archive_id_snapshot=archive.pk, outcome="passed")
    assert restore_drill.due_archive() is None
    assert restore_drill.due_archive(now=timezone.now() + timedelta(days=8)).pk == archive.pk
    PlatformBackupSettings.objects.update(restore_drill_interval_days=0)
    assert restore_drill.due_archive(now=timezone.now() + timedelta(days=8)) is None
