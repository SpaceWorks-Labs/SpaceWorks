"""Gate and object journals retain partial progress across outages and crashes."""

from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.accounts import account_deletion, account_purge_objects as objects
from apps.accounts.models_account_purge import AccountPurgeObject, AccountPurgeProgress
from apps.audit.models import AuditLog
from apps.makerspaces.models import MemberProfile, MemberProject
from apps.tenant_migration.models_source_gate import SourceMigrationGate
from tests.accounts import deletion_factories as f
from tests.accounts.test_support_m1d import account, due, m1d_config, proven, purge
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db(transaction=True)


def close_gate(tenant):
    now = timezone.now()
    return SourceMigrationGate.objects.create(makerspace=tenant, state="quiesced", owner_id=uuid4(),
        heartbeat_at=now, lease_expires_at=now + timedelta(hours=1))


def set_gate(gate, *, closed):
    gate.state = "quiesced" if closed else "open"
    gate.owner_id = uuid4() if closed else None
    gate.save(update_fields=["state", "owner_id"])


def test_gated_tenant_blocks_stage_a_then_partial_purge_resumes_only_unfinished_tenant():
    user, one, two = account(), f.space(), f.space()
    first, second = f.request(user, one), f.request(user, two)
    req = proven(user)
    gate = close_gate(two)
    with pytest.raises(account_deletion.DeletionBlocked) as exc:
        account_deletion.request_deletion(req)
    assert [(b["code"], b["makerspace_id"]) for b in exc.value.blockers] == [("makerspace_gated", two.pk)]
    set_gate(gate, closed=False)
    account_deletion.request_deletion(req)
    user.refresh_from_db()
    due(user)
    set_gate(gate, closed=True)
    assert purge(user) == {"purged": 0, "failed": 0, "skipped": 1}
    progress = AccountPurgeProgress.objects.get(user=user, makerspace=one)
    assert progress.done_at and user.email and user.account_purged_at is None
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.requester_username == user.deletion_username
    assert second.requester_username == user.username
    first_done = progress.done_at
    assert purge(user)["skipped"] == 1
    set_gate(gate, closed=False)
    assert purge(user) == {"purged": 1, "failed": 0, "skipped": 0}
    progress.refresh_from_db()
    second.refresh_from_db()
    assert progress.done_at == first_done
    assert second.requester_username == user.username
    assert AccountPurgeProgress.objects.get(user=user, makerspace=two).done_at
    assert AuditLog.objects.filter(action="account.tenant_purged", target_id=str(user.pk)).count() == 2


@pytest.mark.parametrize("failure", ["head", "delete", "quota"])
def test_profile_images_keep_durable_keys_and_sizes_until_retry(failure, monkeypatch):
    user, tenant = due(account()), f.space()
    membership = assign_builtin_roles(user, tenant, "member")
    profile = MemberProfile.objects.create(membership=membership, avatar_key="member/avatar.png")
    project = MemberProject.objects.create(profile=profile, title="Private project", image_key="member/project.png")
    tenant.storage_bytes_used = 50
    tenant.save(update_fields=["storage_bytes_used"])
    monkeypatch.setattr(objects.limits, "is_self_host", lambda: False)
    head = Mock(return_value=25, side_effect=OSError("storage failed") if failure == "head" else None)
    delete = Mock(side_effect=OSError("storage failed") if failure == "delete" else None)
    real_free = objects.limits.free_storage
    free = Mock(side_effect=OSError("quota failed") if failure == "quota" else real_free)
    monkeypatch.setattr("apps.accounts.account_purge_scrub.public_image_storage.object_size", head)
    monkeypatch.setattr(objects, "_client", Mock())
    monkeypatch.setattr(objects, "delete_all_versions", delete)
    monkeypatch.setattr(objects.limits, "free_storage", free)
    purge(user)
    tenant.refresh_from_db()
    assert user.account_purged_at is None and tenant.storage_bytes_used == 50
    journals = AccountPurgeObject.objects.filter(user=user)
    if failure == "head":
        assert not journals.exists()
        profile.refresh_from_db()
        project.refresh_from_db()
        assert profile.avatar_key == "member/avatar.png" and project.image_key == "member/project.png"
    else:
        assert not MemberProfile.objects.filter(pk=profile.pk).exists()
        assert not MemberProject.objects.filter(pk=project.pk).exists()
        assert set(journals.values_list("object_key", "size_bytes")) == {
            ("member/avatar.png", 25), ("member/project.png", 25)}
        assert journals.filter(quota_released_at__isnull=True).count() == 2
        assert not AccountPurgeProgress.objects.get(user=user, makerspace=tenant).done_at
    head.side_effect = delete.side_effect = None
    free.side_effect = real_free
    assert purge(user)["purged"] == 1
    tenant.refresh_from_db()
    assert tenant.storage_bytes_used == 0
    assert journals.filter(quota_released_at__isnull=True).count() == 0
    calls = delete.call_count, free.call_count
    assert purge(user)["purged"] == 0
    assert (delete.call_count, free.call_count) == calls


def test_gate_closure_keeps_object_journal_pending_and_reopen_drains_it(monkeypatch):
    user, tenant = due(account()), f.space()
    row = AccountPurgeObject.objects.create(user=user, makerspace=tenant,
        bucket="public-images", object_key="member/retry.png", size_bytes=31)
    gate = close_gate(tenant)
    delete, free = Mock(), Mock()
    monkeypatch.setattr(objects, "_client", Mock())
    monkeypatch.setattr(objects, "delete_all_versions", delete)
    monkeypatch.setattr(objects.limits, "free_storage", free)
    assert purge(user)["skipped"] == 1
    row.refresh_from_db()
    assert row.deleted_at is row.quota_released_at is None and row.attempts == 0
    delete.assert_not_called()
    free.assert_not_called()
    set_gate(gate, closed=False)
    assert purge(user)["purged"] == 1
    row.refresh_from_db()
    assert row.deleted_at and row.quota_released_at
    free.assert_called_once()


def test_worker_crash_after_committed_object_deletion_resumes_quota_exactly_once(monkeypatch):
    from apps.accounts import account_purge
    user, tenant = due(account()), f.space()
    tenant.storage_bytes_used = 37
    tenant.save(update_fields=["storage_bytes_used"])
    monkeypatch.setattr(objects.limits, "is_self_host", lambda: False)
    row = AccountPurgeObject.objects.create(user=user, makerspace=tenant,
        bucket="public-images", object_key="member/crash.png", size_bytes=37)
    delete = Mock()
    monkeypatch.setattr(objects, "_client", Mock())
    monkeypatch.setattr(objects, "delete_all_versions", delete)
    real_release = objects.release_quota
    # BaseException models process death: ordinary retry handlers cannot catch it.
    monkeypatch.setattr(objects, "release_quota", Mock(side_effect=SystemExit("worker stopped")))
    with pytest.raises(SystemExit):
        account_purge.purge_account(user.pk, {"purged": 0, "skipped": 0, "failed": 0})
    row.refresh_from_db()
    assert row.deleted_at and row.quota_released_at is None and row.size_bytes == 37
    monkeypatch.setattr(objects, "release_quota", real_release)
    assert purge(user)["purged"] == 1
    assert purge(user)["purged"] == 0
    tenant.refresh_from_db()
    assert tenant.storage_bytes_used == 0
    delete.assert_called_once()
