"""Credential revocation is account-owned, atomic and terminal."""

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.credential_revocation import revoke_all_credentials, revoke_sessions_only
from apps.accounts.models import (
    User, EmailVerificationChallenge, PhoneVerificationChallenge, MFAChallenge,
    OidcBrowserAttempt, SocialLoginNonce, PasswordResetEnvelope, StaffInvitation,
    ReauthenticationSession,
)
from apps.accounts.models_devices import (
    DeviceGrant, DeviceRefreshFamily, DeviceRefreshToken, NativeAppRegistration,
)
from apps.accounts.services_password_reset_drain import EnvelopeClaim, finalize_delivery
from apps.accounts.oidc_browser_attempts import consume_attempt, _digest as oidc_digest, OidcAttemptRejected
from apps.accounts.social_nonces import consume_social_nonce, nonce_digest, SocialNonceRejected
from apps.accounts.staff_invitation_acceptance import accept as accept_invitation
from apps.accounts.mfa_challenges import digest as challenge_digest, start as start_mfa, _locked as locked_mfa
from apps.apiclients.models import ApiClient
from apps.accounts.web_sessions import create_session, validate_session
from apps.audit.models import AuditLog
from apps.integrations.models_endpoints import (
    ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge,
)
from apps.integrations.models_push import PushDevice
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.models_stations import Station
from apps.makerspaces.models_station_leases import StationOperatorLease
from apps.makerspaces.station_operator_leases import resolve_lease, LEASE_SALT
from django.core import signing

pytestmark = pytest.mark.django_db


def session_for(user):
    session = SessionStore()
    session["_auth_user_id"] = str(user.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    session.save()
    return session.session_key


@pytest.fixture
def credentials():
    now = timezone.now()
    expiry = now + timedelta(hours=1)
    space = Makerspace.objects.create(name="Revocation", slug="revocation")
    user = User.objects.create_user(username="credential-owner", email="shared@example.test",
                                    password="Revocation test password 35!")
    membership = MakerspaceMembership.objects.create(
        user=user, makerspace=space,
        assigned_role=MakerspaceRole.objects.get(makerspace=space, slug="member"),
    )
    other = User.objects.create_user(username="unrelated", password="Other account 42!")
    api_client = ApiClient.objects.create(created_by=user, makerspace=space,
                                          label="Independent integration", secret_encrypted=b"sealed-secret")
    django_session = session_for(user)
    other_session = session_for(other)
    refresh = RefreshToken.for_user(user)
    create_session(user, refresh)
    raw_refresh = str(refresh)
    other_refresh = RefreshToken.for_user(other)
    app = NativeAppRegistration.objects.create(
        app_id="org.spaceworks.tests", platform="android", environment="development",
        verifier_config_key="tests", status="approved",
    )
    grant = DeviceGrant.objects.create(
        user=user, registration=app, platform=app.platform, app_id=app.app_id,
        environment=app.environment, signing_identity="test-signature",
        attestation_subject_fingerprint="a" * 64, attested_at=now, last_used_at=now,
    )
    family = DeviceRefreshFamily.objects.create(user=user, grant=grant)
    native_refresh = DeviceRefreshToken.objects.create(
        family=family, jti="native-refresh", token_fingerprint="b" * 64, expires_at=expiry,
    )
    OutstandingToken.objects.create(user=user, jti=native_refresh.jti, token="native",
                                    created_at=now, expires_at=expiry)
    push = PushDevice.objects.create(user=user, makerspace=space, device_grant=grant,
                                    token_ciphertext="ciphertext", token_fingerprint="c" * 64,
                                    provider="fcm", environment="development")
    station = Station.objects.create(makerspace=space, name="Desk", kind="handover", created_by=other)
    lease = StationOperatorLease.objects.create(
        makerspace=space, station=station, actor=user, station_session_id=uuid.uuid4(),
        station_version=1, allowed_actions=["return_request"], issued_at=now, expires_at=expiry,
    )
    mfa_start = start_mfa(user, context={"origin": "https://example.test", "surface": "member"})
    mfa = MFAChallenge.objects.get(token_digest=challenge_digest(mfa_start["challenge"]))
    intent = MFAChallenge.objects.create(
        user=user, token_digest="g" * 64, credential_fingerprint="e" * 64,
        auth_generation="f" * 64, mfa_version=uuid.uuid4(), expires_at=expiry,
        context={"purpose": "social_reauth"},
    )
    email = EmailVerificationChallenge.objects.create(user=user, email=user.email,
                                                     code_digest="email-secret", expires_at=expiry)
    phones = [PhoneVerificationChallenge.objects.create(
        user=user, purpose=purpose, phone_e164="+14155550123", code_digest="phone-secret",
        expires_at=expiry,
    ) for purpose in ("login", "link")]
    oidc = OidcBrowserAttempt.objects.create(
        provider="oidc:tests", state_digest=oidc_digest("state", "browser-state"),
        nonce_digest=oidc_digest("nonce", "browser-nonce"),
        code_verifier="verifier-secret", redirect_uri="https://example.test/callback",
        origin="https://example.test", intended_user=user, intended_membership=membership,
        expires_at=expiry,
    )
    nonce = SocialLoginNonce.objects.create(
        provider="google", surface="member", delivery="device", client_platform="android",
        nonce_digest=nonce_digest("social-nonce"), device_grant=grant, expires_at=expiry,
    )
    proof = ReauthenticationSession.objects.create(
        user=user, session_id=refresh["sid"], surface="member", auth_generation="f" * 64,
        credential_fingerprint="e" * 64, auth_time=now, social_verified_at=now,
        enrollment_confirmed_at=now,
    )
    envelope = PasswordResetEnvelope.objects.create(
        user=user, email_normalized=user.email, email_fingerprint="k" * 64,
        digest="reset-secret", digest_is_live=True, credential_fingerprint="e" * 64,
        expires_at=expiry, requested_at=now, status="delivering", generation=5,
        claim_owner="worker", claimed_at=now, claim_expires_at=expiry,
    )
    role = MakerspaceRole.objects.get(makerspace=space, slug="inventory_manager")
    invitation = StaffInvitation.objects.create(
        account=user, makerspace=space, role=role, email_ciphertext="not-an-identity-match",
        token_digest=challenge_digest("invitation-token"), expires_at=expiry, created_by=other,
    )
    config = ChannelConfiguration.objects.create(makerspace=space, channel="telegram", provider="telegram")
    endpoint = NotificationEndpoint.objects.create(
        makerspace=space, user=user, configuration=config, channel="telegram", provider="telegram",
        destination="private-chat", provider_subject="private-subject", identity_digest="m" * 64,
        integration_identity="bot", integration_generation=1,
        verified_at=now, consented_at=now, consent_version="v1",
    )
    endpoint_challenge = NotificationEndpointChallenge.objects.create(
        makerspace=space, user=user, configuration=config, integration_identity="bot",
        integration_generation=1, code_digest="n" * 64, expires_at=expiry,
        consented_at=now, consent_version="v1",
    )
    return SimpleNamespace(**locals())


def test_revokes_every_account_owned_credential_and_preserves_other_principals(credentials):
    c = credentials
    validate_session(c.user, c.refresh)
    counts = revoke_all_credentials(c.user, reason="staff_deactivated", actor=c.other)
    c.user.refresh_from_db()
    assert c.user.credential_generation == 1
    assert not Session.objects.filter(session_key=c.django_session).exists()
    assert Session.objects.filter(session_key=c.other_session).exists()
    with pytest.raises(TokenError):
        RefreshToken(c.raw_refresh)
    with pytest.raises(AuthenticationFailed):
        validate_session(c.user, c.refresh)
    assert not OutstandingToken.objects.filter(user=c.user, blacklistedtoken__isnull=True).exists()
    assert not BlacklistedToken.objects.filter(token__user=c.other).exists()
    for row in (c.grant, c.family, c.lease, c.invitation, c.endpoint):
        row.refresh_from_db()
        assert row.revoked_at is not None
    assert c.grant.status == "revoked"
    assert c.endpoint.verification_state == "revoked"
    c.native_refresh.refresh_from_db()
    c.push.refresh_from_db()
    assert c.native_refresh.blacklisted_at is not None
    assert not c.push.active and c.push.invalidated_at
    for row in (c.mfa, c.intent, c.email, *c.phones, c.oidc, c.nonce, c.endpoint_challenge):
        row.refresh_from_db()
        assert row.consumed_at is not None
    assert not c.email.is_usable(timezone.now())
    assert all(not phone.is_usable(timezone.now()) for phone in c.phones)
    c.proof.refresh_from_db()
    assert c.proof.auth_time is c.proof.social_verified_at is c.proof.enrollment_confirmed_at is None
    assert c.proof.credential_fingerprint == ""
    c.envelope.refresh_from_db()
    assert not c.envelope.digest_is_live and c.envelope.status == "discarded"
    assert c.envelope.digest != "reset-secret" and c.envelope.generation == 6
    assert not finalize_delivery(EnvelopeClaim(c.envelope.pk, 5, c.user.email), delivered=True)
    c.app.refresh_from_db()
    assert c.app.status == "approved"  # Account revocation cannot revoke an installation.
    assert Station.objects.filter(pk=c.station.pk).exists()
    c.api_client.refresh_from_db()
    assert c.api_client.is_active and bytes(c.api_client.secret_encrypted) == b"sealed-secret"
    event = AuditLog.objects.get(action="account.credentials_revoked", target_id=str(c.user.pk))
    assert event.actor_id == c.other.pk
    assert event.meta == {"reason": "staff_deactivated", "scope": "all", "counts": counts}
    assert all(counts[name] > 0 for name in counts)
    assert "secret" not in str(event.meta) and "private-chat" not in str(event.meta)


def test_revoked_browser_attempts_invitation_and_lease_cannot_be_redeemed(credentials):
    c = credentials
    request = SimpleNamespace(headers={"Origin": "https://example.test"}, device_grant=c.grant)
    token = signing.dumps({
        "lease_id": str(c.lease.pk), "station_id": c.station.pk,
        "session_id": str(c.lease.station_session_id), "version": 1,
    }, salt=LEASE_SALT)
    assert locked_mfa(c.mfa_start["challenge"], request)[0].pk == c.mfa.pk
    revoke_all_credentials(c.user, reason="deactivated")
    with pytest.raises(AuthenticationFailed):
        locked_mfa(c.mfa_start["challenge"], request)
    with pytest.raises(OidcAttemptRejected):
        consume_attempt(request, state="browser-state", nonce="browser-nonce", provider="oidc:tests")
    with pytest.raises(SocialNonceRejected):
        consume_social_nonce(request, raw="social-nonce", provider="google", surface="member",
                             delivery="device", client_platform="android")
    with pytest.raises(ValidationError):
        accept_invitation(SimpleNamespace(user=c.user), token="invitation-token", makerspace_slug=c.space.slug)
    with pytest.raises(PermissionDenied):
        resolve_lease(token, station=c.station, credential=SimpleNamespace(version=1),
                       session_id=c.lease.station_session_id, user=c.user)


def test_repeating_revocation_keeps_terminal_rows_and_timestamps(credentials):
    c = credentials
    revoke_all_credentials(c.user, reason="retired")
    c.invitation.refresh_from_db()
    c.envelope.refresh_from_db()
    timestamp, envelope_generation = c.invitation.revoked_at, c.envelope.generation
    counts = revoke_all_credentials(c.user, reason="retired")
    assert all(count == 0 for count in counts.values())
    c.invitation.refresh_from_db()
    c.envelope.refresh_from_db()
    c.user.refresh_from_db()
    assert c.user.credential_generation == 2
    assert c.invitation.revoked_at == timestamp
    assert c.envelope.generation == envelope_generation
    assert AuditLog.objects.filter(action="account.credentials_revoked", target_id=str(c.user.pk)).count() == 2


def test_sessions_only_preserves_pending_proofs_and_personal_endpoints(credentials):
    c = credentials
    counts = revoke_sessions_only(c.user, reason="admin_password_set")
    assert counts["staff_invitations"] == 1 and counts["device_grants"] == 1
    assert not Session.objects.filter(session_key=c.django_session).exists()
    with pytest.raises(TokenError):
        RefreshToken(c.raw_refresh)
    for row in (c.mfa, c.intent, c.email, *c.phones, c.oidc, c.nonce, c.endpoint_challenge):
        row.refresh_from_db()
        assert row.consumed_at is None
    for row in (c.lease, c.endpoint):
        row.refresh_from_db()
        assert row.revoked_at is None
    c.envelope.refresh_from_db()
    assert c.envelope.digest_is_live and c.envelope.generation == 5
    assert c.user.credential_generation == 1


def test_audit_failure_rolls_back_all_revocations(credentials, monkeypatch):
    c = credentials
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("apps.accounts.credential_revocation.audit.record", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        revoke_all_credentials(c.user, reason="deactivated")
    c.user.refresh_from_db()
    assert c.user.credential_generation == 0
    assert Session.objects.filter(session_key=c.django_session).exists()
    assert not BlacklistedToken.objects.filter(token__user=c.user).exists()
    for row in (c.invitation, c.endpoint, c.lease):
        row.refresh_from_db()
        assert row.revoked_at is None
    c.mfa.refresh_from_db()
    assert c.mfa.consumed_at is None


@pytest.mark.parametrize("status", ["pending", "claimed", "delivering", "issued"])
def test_reset_queue_and_delivery_generations_are_fenced(credentials, status):
    c = credentials
    PasswordResetEnvelope.objects.filter(pk=c.envelope.pk).update(status=status)
    revoke_all_credentials(c.user, reason="deactivated")
    c.envelope.refresh_from_db()
    assert c.envelope.status == "discarded" and not c.envelope.digest_is_live
    assert c.envelope.generation == 6
    assert c.envelope.claim_owner == "" and c.envelope.claim_expires_at is None


def test_open_invitations_are_selected_by_account_not_email(credentials):
    c = credentials
    # Staff and member accounts may share an address; ownership is the FK alone.
    from tests.accounts.account_factories import make_staff

    shared_email_staff = make_staff(c.space, username="staff.same-address",
                                   email=c.user.email, role_slug="inventory_manager")
    other_invitation = StaffInvitation.objects.create(
        account=shared_email_staff, makerspace=c.space, role=c.role,
        email_ciphertext=c.invitation.email_ciphertext, token_digest="o" * 64,
        expires_at=c.expiry, created_by=c.other,
    )
    revoke_sessions_only(c.user, reason="password_set")
    other_invitation.refresh_from_db()
    assert other_invitation.revoked_at is None
    revoke_all_credentials(shared_email_staff, reason="deactivated")
    other_invitation.refresh_from_db()
    assert other_invitation.revoked_at is not None


@pytest.mark.parametrize("reason", [None, "", " ", "x" * 201])
def test_reason_is_validated_before_mutation(credentials, reason):
    with pytest.raises(ValueError):
        revoke_all_credentials(credentials.user, reason=reason)
    credentials.user.refresh_from_db()
    assert credentials.user.credential_generation == 0
