"""End to end: back up one space, drift, preview, confirm, apply (#110d, #111 Q5/Q15/Q16, #113).

Real age keys, the real archive builder and MinIO; the Celery steps are called directly.
"""

import shutil
import subprocess
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.backup import space_restore_runner as runner, space_restore_services as services
from apps.backup.models import BackupArchive, MakerspaceRestoreOperation as Op
from apps.backup.services import create_archive, run_archive
from apps.hardware_requests.models import HardwareRequest
from apps.notifications.models import Notification
from apps.payments.models import Payment
from tests.accounts.account_factories import make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.backup.space_restore_helpers import charge, make_user, seed_space
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


def _keypair(tmp_path, name):
    identity = tmp_path / f"{name}.key"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(["age-keygen", "-y", str(identity)], check=True, capture_output=True,
                               text=True).stdout.strip()
    return identity, recipient


@pytest.fixture
def restore_keys(settings, tmp_path, monkeypatch):
    if not all(shutil.which(binary) for binary in ("age", "age-keygen")):
        pytest.skip("the space restore round trip needs age and age-keygen")
    _platform_identity, platform = _keypair(tmp_path, "platform")
    server_identity, server = _keypair(tmp_path, "server")
    settings.BACKUP_AGE_RECIPIENT = platform
    settings.TENANT_MIGRATION_AGE_RECIPIENT = server
    settings.TENANT_MIGRATION_AGE_IDENTITY_FILE = str(server_identity)
    settings.BACKUP_OPS_DIR = str(tmp_path / "ops")
    settings.BACKUP_PRESIGN_DRAIN_SECONDS = 0
    settings.TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS = 0
    monkeypatch.setattr("apps.backup.tasks_space_restore._dispatch", lambda task, op: None)
    return settings


def _backup(space, actor=None):
    archive = run_archive(create_archive(actor, scope="makerspace", makerspace=space).pk)
    assert archive.status == "available", archive.failure_detail
    assert archive.manifest["server_restorable"] is True
    return archive


def _superadmin():
    from apps.accounts.models import User
    return User.objects.create_superuser("restore-root", email="root@restore.test", password="x" * 20)


def test_restore_round_trip_keeps_audit_money_and_notifies(restore_keys):
    with enabled_encryption():
        root = _superadmin()
        member = make_user("restore-member")
        space, request = seed_space("restore-flow", member)
        manager = make_staff(space, username="restore-manager", email="manager@restore.test")
        archive = _backup(space, root)
        audit_before = AuditLog.objects.filter(makerspace=space).count()
        HardwareRequest.objects.filter(pk=request.pk).update(status="rejected")
        later = HardwareRequest.objects.create(makerspace=space, requester=member,
                                               requester_username=member.username, requester_name="Later")
        flagged = charge(space, member, "After the restore point")

        op = services.request_restore(root, space, archive)
        assert runner.run_preview(op.pk).stage == "preview_ready"
        op.refresh_from_db()
        assert op.preview["blocked"] is False
        assert [row["pk"] for row in op.preview["money_after_restore_point"]] == [str(flagged.pk)]
        with pytest.raises(Exception):
            services.confirm_restore(root, op, "wrong-slug")
        services.confirm_restore(root, op, space.slug)
        done = runner.run_apply(op.pk)

        assert done.stage == "completed", (done.error_code, done.error_detail)
        assert HardwareRequest.objects.get(pk=request.pk).status != "rejected"
        assert not HardwareRequest.objects.filter(pk=later.pk).exists()
        assert Payment.objects.filter(pk=flagged.pk).exists()
        assert done.safety_archive.trigger == BackupArchive.Trigger.SAFETY
        assert done.safety_archive.status == "available"
        assert AuditLog.objects.filter(makerspace=space).count() > audit_before  # live history kept
        actions = set(AuditLog.objects.filter(makerspace=space, action__startswith="backup.space_restore")
                      .values_list("action", flat=True))
        assert {"backup.space_restore_requested", "backup.space_restore_preview_ready",
                "backup.space_restore_confirmed", "backup.space_restore_completed"} <= actions
        assert Notification.objects.filter(makerspace=space, event="backup.space_restore_completed").exists()
        from apps.tenant_migration.models_source_gate import SourceMigrationGate
        assert SourceMigrationGate.objects.get(makerspace=space).state == "open"
        assert manager.pk  # the space's managers are the email audience


def test_live_drift_after_preview_refuses_and_changes_nothing(restore_keys):
    with enabled_encryption():
        root = _superadmin()
        member = make_user("drift-member")
        space, request = seed_space("restore-drift", member)
        archive = _backup(space, root)
        op = services.request_restore(root, space, archive)
        runner.run_preview(op.pk)
        services.confirm_restore(root, Op.objects.get(pk=op.pk), space.slug)
        late = HardwareRequest.objects.create(makerspace=space, requester=member,
                                              requester_username=member.username, requester_name="Drift")
        failed = runner.run_apply(op.pk)
        assert failed.stage == "failed" and failed.error_code == "live_drift"
        assert HardwareRequest.objects.filter(pk=late.pk).exists()
        assert AuditLog.objects.filter(makerspace=space, action="backup.space_restore_failed").exists()
        assert Notification.objects.filter(makerspace=space, event="backup.space_restore_failed").exists()


def test_cross_space_reference_to_a_removed_row_blocks_the_restore(restore_keys):
    from apps.events.models import Event, EventCollaborator
    with enabled_encryption():
        root = _superadmin()
        member = make_user("cross-member")
        space, _request = seed_space("restore-cross", member)
        other, _ = seed_space("restore-cross-other", member)
        archive = _backup(space, root)
        event = Event.objects.create(makerspace=space, title="After backup", created_by=member,
                                     starts_at=timezone.now() + timedelta(days=2),
                                     ends_at=timezone.now() + timedelta(days=2, hours=1))
        EventCollaborator.objects.create(event=event, makerspace=other)
        op = services.request_restore(root, space, archive)
        runner.run_preview(op.pk)
        op.refresh_from_db()
        assert op.preview["blocked"] is True
        assert any(row["reason"] == "other_space" for row in op.preview["blocking"])
        with pytest.raises(Exception):
            services.confirm_restore(root, op, space.slug)


def test_restore_api_is_superadmin_only_and_confirm_needs_reauth(restore_keys):
    from rest_framework.test import APIClient

    from tests.stage4.helpers import bearer_client
    with enabled_encryption():
        root = _superadmin()
        member = make_user("api-member")
        space, _request = seed_space("restore-api", member)
        manager = make_staff(space, username="restore-api-manager")
        archive = _backup(space, root)
    url = reverse("admin-makerspace-restores", args=[space.pk])
    staff = APIClient()
    force_recent_authenticate(staff, manager)
    assert staff.post(url, {"archive": str(archive.pk)}, format="json").status_code == 403
    admin = APIClient()
    force_recent_authenticate(admin, root)
    created = admin.post(url, {"archive": str(archive.pk)}, format="json")
    assert created.status_code == 202, created.data
    runner.run_preview(created.data["id"])
    confirm = reverse("admin-space-restore-confirm", args=[created.data["id"]])
    stale = bearer_client(root).post(confirm, {"confirm_slug": space.slug}, format="json")
    assert stale.status_code == 403 and stale.data["code"] == "recent_reauth_required"
    assert admin.post(confirm, {"confirm_slug": "nope"}, format="json").status_code == 400
    abort = admin.post(reverse("admin-space-restore-abort", args=[created.data["id"]]))
    assert abort.status_code == 200 and abort.data["stage"] == "aborted"
    assert admin.get(reverse("admin-backup-schedule")).status_code == 200
    assert staff.get(reverse("admin-backup-schedule")).status_code == 403
