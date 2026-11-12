"""Database-only terminal transitions used by account credential revocation."""

from django.contrib.sessions.models import Session
from django.db.models import F, Q
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import (
    EmailVerificationChallenge, MFAChallenge, OidcBrowserAttempt,
    PasswordResetEnvelope, PasswordResetEnvelopeStatus, PhoneVerificationChallenge,
    ReauthenticationSession, SocialLoginNonce, StaffInvitation,
)
from apps.accounts.models_devices import DeviceGrant, DeviceRefreshFamily
from apps.accounts.password_reset_crypto import new_dummy_digest
from apps.accounts.services_tokens import blacklist_device_family, revoke_device_grant
from apps.integrations.models_endpoints import NotificationEndpoint, NotificationEndpointChallenge
from apps.makerspaces.models_station_leases import StationOperatorLease


def revoke_authentication(user, *, now, revoke_invitations=True):
    counts = {"django_sessions": 0, "outstanding_tokens": 0}
    # Django's database session store has no indexed user FK. Decode with Django's
    # signature verification; never match text inside the serialized session data.
    for session in Session.objects.all().iterator():
        if str(session.get_decoded().get("_auth_user_id", "")) == str(user.pk):
            session.delete()
            counts["django_sessions"] += 1
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        counts["outstanding_tokens"] += int(created)
    grants = list(DeviceGrant.objects.filter(user=user, status=DeviceGrant.Status.ACTIVE))
    families = list(DeviceRefreshFamily.objects.filter(user=user, revoked_at__isnull=True))
    from apps.integrations.models_push import PushDevice
    # Count before the grants go: revoking a grant already invalidates its push destinations,
    # so counting afterwards would report zero for devices this revocation did switch off.
    live_push = list(PushDevice.objects.filter(user=user, active=True).values_list("pk", flat=True))
    for grant in grants:
        revoke_device_grant(grant)  # Also invalidates this grant's push destinations.
    # Include families whose grants were already revoked by a prior operation.
    for family in families:
        if DeviceRefreshFamily.objects.filter(pk=family.pk, revoked_at__isnull=True).exists():
            blacklist_device_family(family)
    counts["device_grants"] = len(grants)
    counts["refresh_families"] = len(families)
    PushDevice.objects.filter(user=user, active=True).update(active=False, invalidated_at=now)
    counts["push_devices"] = len(live_push)
    # S-B: every remembered device is forgotten with the sessions it signed in.
    from apps.accounts.device_memory import revoke_all
    counts["known_devices"] = revoke_all(user, now=now)
    counts.update(revoke_person_credentials(user, now=now))
    if revoke_invitations:
        counts["staff_invitations"] = StaffInvitation.objects.filter(
            account=user, accepted_at__isnull=True, revoked_at__isnull=True,
        ).update(revoked_at=now)
    return counts


# Library-owned OAuth rows, dependants first (AccessToken points at RefreshToken and IDToken).
_OAUTH_TOKEN_LABELS = ("oauth2_provider.RefreshToken", "oauth2_provider.AccessToken",
                       "oauth2_provider.IDToken", "oauth2_provider.Grant", "oauth2_provider.DeviceGrant")


def revoke_person_credentials(user, *, now):
    """#196 bearers that act as the person: PATs end; app connections are disconnected."""
    from django.apps import apps
    counts = {"personal_access_tokens": 0, "oauth_tokens": 0, "oauth_consents": 0}
    if apps.is_installed("apps.apiclients"):
        from apps.apiclients.models_tokens import OAuthConsent, PersonalAccessToken
        counts["personal_access_tokens"] = PersonalAccessToken.objects.filter(
            user=user, revoked_at__isnull=True,
        ).update(revoked_at=now)
        counts["oauth_consents"] = OAuthConsent.objects.filter(user=user).delete()[0]
    if apps.is_installed("oauth2_provider"):
        for label in _OAUTH_TOKEN_LABELS:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            counts["oauth_tokens"] += model.objects.filter(user=user).delete()[0]
    return counts


def revoke_pending_proofs(user, *, now):
    counts = {}
    pending = (
        ("mfa_challenges", MFAChallenge.objects.filter(user=user)),
        ("email_challenges", EmailVerificationChallenge.objects.filter(user=user)),
        ("phone_challenges", PhoneVerificationChallenge.objects.filter(user=user)),
        ("oidc_attempts", OidcBrowserAttempt.objects.filter(intended_user=user)),
        ("social_nonces", SocialLoginNonce.objects.filter(device_grant__user=user)),
        ("endpoint_challenges", NotificationEndpointChallenge.objects.filter(user=user)),
    )
    for name, rows in pending:
        counts[name] = rows.filter(consumed_at__isnull=True).update(consumed_at=now)
    counts["reauthentication_proofs"] = ReauthenticationSession.objects.filter(user=user).filter(
        Q(auth_time__isnull=False) | Q(social_verified_at__isnull=False)
        | Q(enrollment_confirmed_at__isnull=False) | ~Q(credential_fingerprint=""),
    ).update(auth_time=None, social_verified_at=None, enrollment_confirmed_at=None,
             credential_fingerprint="")
    counts["station_operator_leases"] = StationOperatorLease.objects.filter(
        actor=user, revoked_at__isnull=True,
    ).update(revoked_at=now)
    counts["notification_endpoints"] = NotificationEndpoint.objects.filter(
        user=user, revoked_at__isnull=True,
    ).update(revoked_at=now, verification_state="revoked")
    return counts


def revoke_reset_envelopes(envelopes, *, now):
    changed = 0
    active = {
        PasswordResetEnvelopeStatus.PENDING, PasswordResetEnvelopeStatus.CLAIMED,
        PasswordResetEnvelopeStatus.DELIVERING, PasswordResetEnvelopeStatus.ISSUED,
    }
    for envelope in envelopes:
        if envelope.status not in active and not envelope.digest_is_live:
            continue
        changed += PasswordResetEnvelope.objects.filter(pk=envelope.pk).update(
            status=PasswordResetEnvelopeStatus.DISCARDED, digest_is_live=False,
            digest=new_dummy_digest(envelope.email_normalized),
            credential_fingerprint="", expires_at=None, superseded_at=now, terminal_at=now,
            claimed_at=None, claim_owner="", claim_expires_at=None,
            generation=F("generation") + 1,
        )
    return changed
