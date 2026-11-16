"""Pending Apple revocation must never touch a credential obtained after restore."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.accounts import apple_credentials as credentials, apple_revocation as revocation
from apps.accounts.account_restore_email import confirm_email
from apps.accounts.models import SocialIdentity
from apps.accounts.models_account_purge import AppleRefreshCredential, AppleRevocation
from apps.makerspaces.secrets import encrypt_value, decrypt_value
from tests.accounts.restore_helpers_m1d import PASSWORD, archive, email_proof, restore_config
from tests.accounts.test_support_m1d import account, m1d_config

pytestmark = pytest.mark.django_db


def test_stage_a_captures_encrypted_token_and_version_then_worker_revokes_only_old_token(monkeypatch):
    user = account()
    identity = SocialIdentity.objects.create(user=user, provider="apple", provider_sub="linked")
    credential = AppleRefreshCredential.objects.create(social_identity=identity, client_id="web.service",
                                                       token_ciphertext=encrypt_value("old-refresh"))
    captured_version = credential.version
    archive(user)
    work = AppleRevocation.objects.get(user=user)
    assert work.credential_id == credential.pk and work.credential_version == captured_version
    assert decrypt_value(work.token_ciphertext) == "old-refresh" and work.token_ciphertext != "old-refresh"
    confirm_email(user.email, email_proof(user), PASSWORD)
    user.refresh_from_db()
    monkeypatch.setattr(credentials, "client_secret", lambda client: "client-secret")
    monkeypatch.setattr(credentials, "apple_post", Mock(return_value={"id_token": "signed", "refresh_token": "new-refresh"}))
    monkeypatch.setattr(credentials, "decode_rs256_token", lambda *a, **kw: {"sub": "linked"})
    credentials.store_refresh_credential(user, {"sub": "linked", "aud": "web.service"}, "fresh-signin-code")
    credential.refresh_from_db()
    assert credential.version != captured_version and decrypt_value(credential.token_ciphertext) == "new-refresh"
    revoke = Mock()
    monkeypatch.setattr(revocation, "client_secret", lambda client: "client-secret")
    monkeypatch.setattr(revocation, "apple_post", revoke)
    revocation.sweep_revocations(user.pk)
    assert revoke.call_args.args[1]["token"] == "old-refresh"
    credential.refresh_from_db()
    assert decrypt_value(credential.token_ciphertext) == "new-refresh"
    work.refresh_from_db()
    assert work.done_at and work.token_ciphertext == ""
    revocation.sweep_revocations(user.pk)
    assert revoke.call_count == 1


def test_multiple_departures_keep_each_apple_token_snapshot_separate(monkeypatch):
    from uuid import uuid4
    from apps.accounts.account_deletion import request_deletion
    from apps.accounts import reauthentication
    from tests.accounts.test_reauthentication import request
    user = account()
    identity = SocialIdentity.objects.create(user=user, provider="apple", provider_sub="linked")
    credential = AppleRefreshCredential.objects.create(social_identity=identity, client_id="web.service",
                                                       token_ciphertext=encrypt_value("first-refresh"))
    archive(user)
    confirm_email(user.email, email_proof(user), PASSWORD)
    user.refresh_from_db()
    credential.version = uuid4()
    credential.token_ciphertext = encrypt_value("second-refresh")
    credential.save()
    req = request(user, surface="member")
    reauthentication.verify(req, password=PASSWORD)
    request_deletion(req)
    rows = list(AppleRevocation.objects.filter(user=user).order_by("pk"))
    assert len(rows) == 2 and rows[0].credential_version != rows[1].credential_version
    assert [decrypt_value(row.token_ciphertext) for row in rows] == ["first-refresh", "second-refresh"]
    revoke = Mock()
    monkeypatch.setattr(revocation, "apple_post", revoke)
    monkeypatch.setattr(revocation, "client_secret", lambda client: "client-secret")
    for row in rows:
        revocation.revoke_one(row.pk)
    assert [call.args[1]["token"] for call in revoke.call_args_list] == ["first-refresh", "second-refresh"]


def test_revocation_retry_after_restore_is_bound_to_its_original_deadline(monkeypatch):
    user = account()
    identity = SocialIdentity.objects.create(user=user, provider="apple", provider_sub="linked")
    credential = AppleRefreshCredential.objects.create(social_identity=identity, client_id="web.service",
                                                       token_ciphertext=encrypt_value("old-refresh"))
    archive(user)
    row = AppleRevocation.objects.get(user=user)
    confirm_email(user.email, email_proof(user), PASSWORD)
    revoke = Mock(side_effect=OSError("outage"))
    monkeypatch.setattr(revocation, "apple_post", revoke)
    monkeypatch.setattr(revocation, "client_secret", lambda client: "client-secret")
    revocation.revoke_one(row.pk)
    row.refresh_from_db()
    assert row.attempts == 1 and not row.done_at
    row.created_at = timezone.now() - timedelta(days=81)
    row.save(update_fields=["created_at"])
    revocation.sweep_revocations(user.pk)
    row.refresh_from_db()
    assert row.done_at and row.last_error == "retention_deadline" and row.token_ciphertext == ""
    assert AppleRefreshCredential.objects.filter(pk=credential.pk).exists()
    assert revoke.call_count == 1
