"""Invalidate account bearers and second-factor secrets in the departure transaction."""

from django.apps import apps
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.accounts.models import EmailVerificationChallenge
from apps.accounts.models_devices import DeviceRefreshFamily
from apps.accounts.models_mfa import MFAChallenge, UserMFA
from apps.accounts.models_password_reset import PasswordResetEnvelope
from apps.accounts.models_phone import PhoneVerificationChallenge
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.services_tokens import blacklist_device_family, blacklist_outstanding_tokens


def revoke(user, now):
    blacklist_outstanding_tokens(user)
    # Also fence malformed/legacy state where a family outlived a revoked grant.
    for family in DeviceRefreshFamily.objects.filter(user=user, revoked_at__isnull=True):
        blacklist_device_family(family, revoke_grant=True)
    ReauthenticationSession.objects.filter(user=user).delete()
    MFAChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    EmailVerificationChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    PhoneVerificationChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    PasswordResetEnvelope.objects.filter(user=user).update(
        digest_is_live=False, consumed_at=now, status="discarded", terminal_at=now,
    )
    # Database-backed control/browser sessions have no User FK. Signed-cookie
    # sessions also lose access immediately because the account is inactive.
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if str(session.get_decoded().get("_auth_user_id", "")) == str(user.pk):
            session.delete()
    # Deployments using DRF personal API tokens must invalidate those too. Tenant
    # HMAC ApiClients are application credentials, not personal account tokens.
    if apps.is_installed("rest_framework.authtoken"):
        apps.get_model("authtoken.Token").objects.filter(user=user).delete()
    try:
        push = apps.get_model("integrations.PushDevice")
    except LookupError:
        push = None
    if push is not None:
        push.objects.filter(user=user, active=True).update(active=False, invalidated_at=now)
    UserMFA.objects.filter(user=user).delete()
