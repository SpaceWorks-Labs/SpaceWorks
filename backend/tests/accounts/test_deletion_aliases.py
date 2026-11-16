"""U-C deletion and purge on one account per person: staff self-deletion, every alias, shred."""

import json
import uuid
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.accounts import account_deletion as service
from apps.accounts import account_purge as purge
from apps.accounts import reauthentication
from apps.accounts.account_deletion_blockers import collect
from apps.accounts.account_deletion_discovery import alias_tenant_ids, tenant_ids
from apps.accounts.models import User
from apps.accounts.models_account_merge import AccountMergeRecord
from apps.accounts.models_account_purge import AccountPurgeProgress
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.secrets import encrypt_value
from tests.accounts import deletion_factories as f
from tests.accounts.account_factories import grant_staff_role, make_membership, make_staff
from tests.accounts.test_reauthentication import PASSWORD, request
from tests.accounts.ua1_helpers import merged_shell

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_DELETION_RETENTION_DAYS = 90


def _proven(user):
    req = request(user, surface="member")
    reauthentication.verify(req, password=PASSWORD)
    return req


def _codes(user):
    return {row["code"] for row in collect(user)}


def test_staff_person_self_deletes_and_staff_rows_are_revoked():
    tenant = f.space()
    manager = make_staff(tenant, username="del-manager", password=PASSWORD)
    make_staff(tenant, username="del-other-manager")
    worker = User.objects.create_user("del-worker", password=PASSWORD, email="worker@example.test")
    grant_staff_role(worker, tenant, role_slug="inventory_manager")
    make_membership(worker, tenant)
    assert tenant.pk in tenant_ids(worker)  # discovery sees the staff track too
    service.request_deletion(_proven(worker))
    rows = MakerspaceMembership.all_tracks.filter(user=worker)
    assert rows.count() == 2 and set(rows.values_list("status", flat=True)) == {"revoked"}
    assert "last_manager" not in _codes(manager)


def test_last_space_manager_is_blocked_on_the_staff_track():
    tenant = f.space()
    manager = make_staff(tenant, username="del-last", password=PASSWORD)
    assert "last_manager" in _codes(manager)
    with pytest.raises(service.DeletionBlocked):
        service.request_deletion(_proven(manager))
    assert MakerspaceMembership.staff_tracks.get(user=manager).status == "active"


def test_obligations_on_a_merged_shell_still_block():
    tenant = f.space()
    survivor = User.objects.create_user("del-survivor", password=PASSWORD)
    source = User.objects.create_user("del-source")
    f.payment(source, tenant)
    merged_shell(source, survivor)
    assert "unpaid_charges" in _codes(survivor)


@pytest.fixture
def deleted_with_shell():
    tenant = f.space()
    person = User.objects.create_user("purge-person", email="purge@example.test")
    shell = User.objects.create_user("purge-shell", email="shell@example.test")
    make_membership(shell, tenant, status="revoked")
    from tests.accounts.merge_helpers import feed
    leftover = feed(tenant, shell)
    f.request(shell, tenant)  # a tenant-local identity copy left on the shell
    record = AccountMergeRecord.objects.create(
        decision="merged", source=shell, target=person, proof_method="email_codes", run_id=uuid.uuid4(),
        snapshot_scheme="deployment", snapshot_ciphertext=encrypt_value(json.dumps({"email": "shell@example.test"})),
        state="completed", completed_at=timezone.now())
    merged_shell(shell, person)
    User.objects.filter(pk=person.pk).update(
        is_active=False, deletion_requested_at=timezone.now() - timedelta(days=91),
        deletion_purge_after=timezone.now() - timedelta(days=1),
        deletion_email_ciphertext=encrypt_value(person.email))
    person.refresh_from_db()
    return tenant, person, shell, leftover, record


def test_purge_covers_every_alias(deleted_with_shell):
    tenant, person, shell, leftover, record = deleted_with_shell
    assert tenant.pk not in tenant_ids(person) and tenant.pk in alias_tenant_ids(person)
    counts = {"purged": 0, "skipped": 0, "failed": 0}
    purge.purge_account(person.pk, counts)
    person.refresh_from_db()
    assert counts["purged"] == 1 and person.account_purged_at is not None
    assert AccountPurgeProgress.objects.filter(user=person, makerspace=tenant, done_at__isnull=False).exists()
    from apps.bookings.models_feed import BookingCalendarFeed
    assert not BookingCalendarFeed.objects.filter(pk=leftover.pk).exists()
    from apps.hardware_requests.models import HardwareRequest
    copy = HardwareRequest.objects.get(requester=shell)
    assert copy.requester_username.startswith("deleted_") and copy.requester_name == ""
    record.refresh_from_db()
    assert record.snapshot_scheme == "scrubbed" and record.snapshot_ciphertext == ""
    assert AuditLog.objects.get(action="account.purged", target_id=str(person.pk)).meta["aliases"] == 1
    # Retained: the shell itself and its revoked membership history.
    assert User.objects.filter(pk=shell.pk, merged_into=person).exists()
    assert MakerspaceMembership.all_tracks.filter(user=shell).exists()


def test_key_shred_is_a_no_op_without_account_keys(deleted_with_shell):
    from apps.accounts.account_purge_aliases import shred_account_keys

    _tenant, person, _shell, _leftover, _record = deleted_with_shell
    assert shred_account_keys(person) is True


def test_restore_never_brings_staff_roles_back(monkeypatch):
    from django.db import transaction

    from apps.accounts.account_restore import restore_locked

    tenant = f.space()
    make_staff(tenant, username="del-keeper")
    worker = make_staff(tenant, username="del-restored", role_slug="inventory_manager", password=PASSWORD)
    service.request_deletion(_proven(worker))
    monkeypatch.setattr("apps.accounts.account_restore.matches", lambda user, fingerprint: True)
    with transaction.atomic():
        restore_locked(User.objects.select_for_update().get(pk=worker.pk), fingerprint="proof",
                       new_password="Restored-Strong-Passphrase-4821")
    assert User.objects.get(pk=worker.pk).is_active
    assert MakerspaceMembership.staff_tracks.get(user=worker).status == "revoked"
