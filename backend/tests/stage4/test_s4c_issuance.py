"""Sweep password, MFA, claim, provider, phone and native issuance boundaries."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts import mfa_challenges
from apps.accounts.credential_revocation import revoke_all_credentials, revoke_sessions_only
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import User
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.services_phone import _digest
from apps.accounts.services_phone_login import confirm_login
from apps.accounts.services_social_login import issue_social_session
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.accounts.services_tokens import revoke_device_grant
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.mfa_helpers import enrolled
from .test_s4c_refresh_revocation import principal, device_tokens

pytestmark = pytest.mark.django_db


def assert_account_first(call):
    queries = []

    def capture(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(capture):
        result = call()
    locks = [sql for sql in queries if "FOR UPDATE" in sql or "FOR NO KEY UPDATE" in sql]
    assert locks and '"accounts_user"' in locks[0], locks
    account_lock = next(i for i, sql in enumerate(queries)
                        if '"accounts_user"' in sql and ("FOR UPDATE" in sql or "FOR NO KEY UPDATE" in sql))
    for i, sql in enumerate(queries):
        if sql.startswith(("INSERT", "UPDATE", "DELETE")) and any(table in sql for table in (
            "token_blacklist_", "accounts_device", "accounts_mfachallenge", "accounts_phoneverificationchallenge",
        )):
            assert account_lock < i, queries
    return result


@pytest.mark.parametrize("kind", ["member", "staff", "platform"])
def test_common_token_issuer_locks_account_and_fences_stale_proofs(kind):
    user = principal(kind)
    assert_account_first(lambda: SpaceWorksRefreshToken.for_user(user))
    stale = User.objects.get(pk=user.pk)
    revoke_sessions_only(User.objects.get(pk=user.pk), reason="s4c.stale-first-factor")
    count = OutstandingToken.objects.count()
    with pytest.raises(AuthenticationFailed):
        SpaceWorksRefreshToken.for_user(stale)
    assert OutstandingToken.objects.count() == count


@pytest.mark.parametrize("delivery", ["web", "device"])
def test_provider_issuance_locks_before_device_rows_and_rejects_stale_accounts(delivery):
    user = principal("member")
    grant = None
    if delivery == "device":
        device_tokens(user)
        grant = user.device_grants.get()
    nonce = SimpleNamespace(device_grant=grant, device_grant_id=grant.pk if grant else None)
    issue = lambda account: issue_social_session(account, surface="member", delivery=delivery, nonce_row=nonce)
    tokens = assert_account_first(lambda: issue(user))
    assert tokens["access"] and tokens["refresh"]
    revoke_all_credentials(User.objects.get(pk=user.pk), reason="s4c.stale-provider")
    count = OutstandingToken.objects.count()
    with pytest.raises(AuthenticationFailed):
        issue(user)
    assert OutstandingToken.objects.count() == count


def test_first_social_device_issuance_locks_before_registration(monkeypatch):
    from tests.device_helpers import make_native_app_registration
    monkeypatch.setattr("apps.accounts.services_device_grants.assert_mobile_grant_creation_enabled", lambda: None)
    registration = make_native_app_registration()
    challenge = SimpleNamespace(registration_id=registration.pk, platform=registration.platform,
        app_id=registration.app_id, environment=registration.environment, signing_identity="s4c")
    nonce = SimpleNamespace(device_grant=None, device_grant_id=None, attestation_challenge=challenge)
    user = principal("member")
    tokens = assert_account_first(lambda: issue_social_session(user, surface="member",
        delivery="device", nonce_row=nonce, verified_attestation=SimpleNamespace(subject="subject", metadata={})))
    assert tokens["device_grant"].status == "active"


def test_device_issuance_checks_live_grant_after_account_lock():
    user = principal("member")
    device_tokens(user)
    grant = user.device_grants.get()
    assert_account_first(lambda: issue_device_token_pair(user, grant))
    revoke_device_grant(grant)
    count = OutstandingToken.objects.count()
    with pytest.raises(AuthenticationFailed):
        issue_device_token_pair(user, grant)
    assert OutstandingToken.objects.count() == count


@pytest.mark.parametrize("kind,surface", [("member", "member"), ("staff", "staff_api"),
                                         ("platform", "platform"), ("platform", "control")])
@pytest.mark.parametrize("revoked", [False, True])
def test_mfa_completion_locks_account_before_proof_and_tokens(kind, surface, revoked):
    user = principal(kind)
    row, secret = enrolled(user)
    request = APIRequestFactory().post("/mfa/control/" if surface == "control" else "/api/v1/auth/mfa/verify",
                                      HTTP_ORIGIN="http://localhost:5000")
    request.user = user
    from apps.accounts.mfa_sessions import context
    challenge = mfa_challenges.start(user, context=context(request, surface=surface))["challenge"]
    if revoked:
        revoke_sessions_only(User.objects.get(pk=user.pk), reason="s4c.pending-mfa")
    code = totp(secret, int(timezone.now().timestamp() // 30))
    count = OutstandingToken.objects.count()
    finish = lambda: mfa_challenges.finish(challenge, code, request)
    if revoked:
        with pytest.raises(AuthenticationFailed):
            assert_account_first(finish)
        assert OutstandingToken.objects.count() == count
    else:
        result = assert_account_first(finish)
        if surface == "control":
            assert result["mfa_version"] == str(row.version)
        else:
            assert result["access"]


def test_phone_confirmation_locks_account_before_consuming_proof():
    user = User.objects.create_user("phone-race", phone_e164="+14155552671", phone_verified_at=timezone.now())
    PhoneVerificationChallenge.objects.create(user=user, purpose="login", phone_e164=user.phone_e164,
        code_digest=_digest("681924", user.phone_e164), expires_at=timezone.now() + timedelta(minutes=5))
    proved = assert_account_first(lambda: confirm_login(user.phone_e164, "681924"))
    revoke_sessions_only(User.objects.get(pk=user.pk), reason="s4c.phone-proof")
    with pytest.raises(AuthenticationFailed):
        SpaceWorksRefreshToken.for_user(proved)


def test_claim_mint_and_rotation_lock_account_before_tokens():
    from apps.accounts.claim_tokens import mint_claim_tokens, rotate_claim_refresh
    from apps.accounts.models import MemberClaimCode
    from apps.makerspaces.models import Makerspace
    from tests.accounts.account_factories import make_membership
    from rest_framework_simplejwt.exceptions import TokenError

    user = User.objects.create_user("claim-user", is_walk_in=True)
    space = Makerspace.objects.create(name="Claim", slug="s4c-claim")
    membership = make_membership(user, space)
    deadline = timezone.now() + timedelta(minutes=30)
    claim = MemberClaimCode.objects.create(membership=membership, code_digest="c" * 64,
        consumed_at=timezone.now(), expires_at=deadline, absolute_expires_at=deadline)
    pair = assert_account_first(lambda: mint_claim_tokens(claim))
    rotated, _actor = assert_account_first(lambda: rotate_claim_refresh(pair.refresh))
    revoke_sessions_only(User.objects.get(pk=user.pk), reason="s4c.claim-refresh")
    with pytest.raises(TokenError):
        rotate_claim_refresh(rotated.refresh)
