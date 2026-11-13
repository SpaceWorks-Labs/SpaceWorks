"""Everyone needs a username (decision 308): the typed `handle_required` gate and the availability check.

The gate runs in `SpaceWorksJWTAuthentication`, i.e. only for HUMAN bearer sessions (web and native
member/staff/event grants). Machine API clients (HMAC) and kiosk/station/display tokens authenticate
through other classes and never reach it, so they are unaffected by construction. It only blocks
state-changing requests, and only for personal accounts that still have no handle; reading your own
account, signing out, refreshing the session and choosing a handle stay open.
"""

from django.utils.translation import gettext
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS

ALLOWED_URL_NAMES = frozenset({
    "auth-logout", "auth-logout-all", "device-logout", "auth-refresh", "device-refresh",
    "member-global-profile-handle", "member-profile-handle", "handle-check",
    # A new sign-up claims its username when the email is confirmed (M14), so verifying is open.
    "auth-email-verification-confirm", "auth-email-verification-resend",
    # Safety and erasure paths are never held hostage to a username (SECURITY-REVIEW M16).
    "auth-account-deletion", "auth-change-password", "auth-reset-password", "auth-forgot-password",
    "auth-mfa", "auth-mfa-confirm", "auth-mfa-disable", "auth-mfa-enroll", "auth-mfa-recovery", "auth-mfa-verify",
    "auth-passkeys", "auth-passkey-detail", "auth-passkeys-register-options", "auth-passkeys-register-verify",
    "auth-reauth", "auth-reauth-passkey", "auth-reauth-passkey-options", "auth-reauth-phone-start",
    "auth-reauth-phone-confirm", "auth-reauth-social-start", "auth-reauth-social-factor",
    "auth-reauth-social-complete", "auth-reauth-enrollment-email", "auth-reauth-enrollment-confirm",
})


class HandleRequired(PermissionDenied):
    default_code = "handle_required"
    default_detail = "Choose your username before continuing."


def assert_handle_chosen(request, user):
    """Raise the typed 403 for a state-changing request by a personal account with no handle."""
    if request.method in SAFE_METHODS:
        return
    from apps.accounts.staff_identity import is_person

    if not is_person(user) or user.is_walk_in or getattr(user, "account_kind", "") != "member":
        return
    from apps.accounts.restricted_admission import restricted_route_admitted
    if restricted_route_admitted(user, request):
        # A restricted person cannot choose a handle, but must still settle their debt.
        return
    if getattr(request.resolver_match, "url_name", None) in ALLOWED_URL_NAMES:
        return
    from .public_profile_handles import has_handle, in_release_cooldown

    # Decision 336e (M16): someone who deliberately released their handle waits 30 days before
    # claiming another; that wait blocks only handle changes, never their other writes.
    if not has_handle(user) and not in_release_cooldown(user):
        # A dict detail is returned as the body, so clients get the typed `code` (DRF drops it otherwise).
        raise HandleRequired({"detail": gettext("Choose your username before continuing."), "code": "handle_required"})


class HandleCheckSerializer(serializers.Serializer):
    handle = serializers.CharField(required=False, allow_blank=True, max_length=60)
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
