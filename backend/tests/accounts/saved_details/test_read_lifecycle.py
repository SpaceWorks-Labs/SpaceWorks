from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.saved_details import access, downloads, lifecycle, prefill, resume_copy
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.models import MemberSavedAsset, SavedDetailsObjectCleanup
from apps.audit.models import AuditLog
from apps.encryption import account_services
from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
from apps.encryption.account_readiness import SavedDetailsUnavailable
from apps.encryption.account_services import AccountKeyUnavailable, prepare_account_key, revoke_account_keys

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def owner(settings):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    settings.PII_ENCRYPTION_ENABLED = False
    return User.objects.create_user(username=f"read-vault-{uuid4().hex}")


def asset_for(owner, *, state="ready", size=1_048_577):
    asset_id = uuid4()
    return MemberSavedAsset.objects.create(user=owner, public_id=asset_id,
        object_key=f"account/{asset_id}/resume.pdf", staging_key=f"staging/{asset_id}",
        verification_key=f"verification/{asset_id}", size_bytes=size, state=state,
        sha256="a" * 64, final_version_id="verified-version")


def test_owner_read_gate_fails_closed_for_missing_owner_key(owner):
    with pytest.raises(AccountKeyUnavailable):
        access.owner_read_gate(owner.pk)


def test_owner_read_gate_rechecks_epoch_without_unwrapping_on_each_check(owner, monkeypatch):
    prepare_account_key(owner.pk)
    authorize = access.owner_read_gate(owner.pk)
    monkeypatch.setattr(account_services, "get_account_key", lambda *_: pytest.fail("Unexpected unwrap"))
    authorize()
    revoke_account_keys(owner.pk, owner)
    with pytest.raises(AccountKeyUnavailable):
        authorize()


def test_retired_owner_cannot_read_assets_or_status(owner, monkeypatch):
    # The database refuses a retired MEMBER outright (trigger and the
    # user_account_context check: only staff shells retire), so feed the gate the
    # loaded row it would see to prove it still refuses as defense in depth.
    from types import SimpleNamespace
    owner.retired_at = timezone.now()
    rows = SimpleNamespace(filter=lambda **_: SimpleNamespace(first=lambda: owner))
    monkeypatch.setattr(access, "get_user_model", lambda: SimpleNamespace(objects=rows))
    with pytest.raises(SavedDetailsError) as error:
        access.require_owner(owner.pk)
    assert error.value.status_code == 403


def test_original_download_stops_before_next_storage_read_after_key_revocation(owner, monkeypatch):
    prepare_account_key(owner.pk)
    asset = asset_for(owner)
    reads = []

    def read(locator, *, start, length, timeout_seconds):
        reads.append((start, length))
        return b"p" * length

    monkeypatch.setattr(downloads.storage, "read_range", read)
    request = SimpleNamespace(user=owner, headers={}, method="GET", auth=None)
    response = downloads.resume_download(request, asset.pk)
    iterator = iter(response.streaming_content)
    assert len(next(iterator)) == 1_048_576
    revoke_account_keys(owner.pk, owner)
    with pytest.raises(AccountKeyUnavailable):
        next(iterator)
    assert len(reads) == 1


def test_copy_to_event_stops_before_next_storage_read_after_key_revocation(owner, monkeypatch):
    prepare_account_key(owner.pk)
    asset = asset_for(owner)
    reads = []

    def read(locator, *, start, length, timeout_seconds):
        reads.append(start)
        return b"p" * length

    monkeypatch.setattr(resume_copy.storage, "read_range", read)
    prepared = resume_copy.prepare_saved_resume_copy(actor_id=owner.pk, asset_id=asset.pk, sha256=asset.sha256)
    assert len(next(prepared.chunks)) == 1_048_576
    revoke_account_keys(owner.pk, owner)
    with pytest.raises(AccountKeyUnavailable):
        next(prepared.chunks)
    assert reads == [0]


def test_empty_vault_prefill_requires_configured_ready_broker(owner, settings):
    settings.ACCOUNT_PII_MASTER_KEY = ""
    with pytest.raises(SavedDetailsUnavailable):
        prefill.prefill(owner.pk, {})


def test_configured_empty_vault_prefill_does_not_provision_owner_key(owner, monkeypatch):
    context = prefill.PrefillContext(owner_id=owner.pk, event_id=42, subject_kind="registration",
        form_id="event-registration", form_revision=1, event_date_revision=1,
        as_of_date=timezone.now().date(), questions=())
    monkeypatch.setattr(prefill, "_provider", SimpleNamespace(resolve=lambda **_: context))
    result = prefill.prefill(owner.pk, {"context": {"event_id": 42, "subject_kind": "registration"},
        "form_id": context.form_id,
        "form_revision": 1, "event_date_revision": 1})
    assert result["values"] == {}
    assert not AccountPiiKey.objects.filter(user=owner).exists()


def test_erase_owner_who_never_initialized_vault_and_prelock_keys_before_assets(owner):
    asset_for(owner)
    with CaptureQueriesContext(connection) as queries:
        lifecycle.erase_account_vault(owner.pk, actor=owner)
    locks = [query["sql"].lower() for query in queries if "for update" in query["sql"].lower()]
    key_lock = next(i for i, sql in enumerate(locks) if "encryption_accountpiikey" in sql)
    asset_lock = next(i for i, sql in enumerate(locks) if "accounts_membersavedasset" in sql)
    assert key_lock < asset_lock
    assert PiiAccountWriteFence.objects.get(user=owner).state == "erased"
    assert not MemberSavedAsset.objects.filter(user=owner).exists()
    assert SavedDetailsObjectCleanup.objects.count() == 1


def test_live_asset_cleanup_is_audited_and_repeated_cleanup_does_not_retransition(owner, monkeypatch):
    prepare_account_key(owner.pk)
    asset = asset_for(owner, state="deleting")
    receipt = SavedDetailsObjectCleanup.objects.create(object_keys=[asset.object_key], next_attempt_at=timezone.now())
    deleted = []
    monkeypatch.setattr(lifecycle.storage, "delete_keys", lambda keys: deleted.append(keys))
    lifecycle.run_object_cleanup(receipt.pk)
    asset.refresh_from_db()
    assert asset.state == "deleted"
    assert asset.version == 2
    assert AuditLog.objects.filter(action="account.saved_resume_cleanup_completed").count() == 1
    SavedDetailsObjectCleanup.objects.filter(pk=receipt.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    lifecycle.run_object_cleanup(receipt.pk)
    assert len(deleted) == 2
    assert AuditLog.objects.filter(action="account.saved_resume_cleanup_completed").count() == 1
