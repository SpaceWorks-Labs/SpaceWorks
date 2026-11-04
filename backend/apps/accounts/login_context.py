"""Resolve the password door's account before authenticating it (one account per person).

There is one door and no account context or makerspace field: a person signs in with
their username or their email (a converted staff account's email that was put on hold
is blank, so only its username works). Turning member password sign-in off never locks
out a person who holds a staff role. The platform superadmin is a separate account,
reachable only from a configured platform origin (``PLATFORM_STAFF_ORIGINS``) and only by
username or by an email no person holds, so a person's address never selects it.
"""

from django.conf import settings
from django.db.models import Q
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.models import User
from apps.accounts.staff_identity import has_staff_role, is_platform, person_q, platform_q
from apps.accounts.surface_policy import assert_surface

_REFUSED = "No active account found with the given credentials"


def _platform_origin(request):
    from apps.accounts.social_nonces import request_origin

    return request is not None and request_origin(request) in settings.PLATFORM_STAFF_ORIGINS


def resolve_identifier(identifier, request):
    """The one account this identifier names at this door, or None."""
    live = User.objects.filter(is_active=True, retired_at__isnull=True, merged_into__isnull=True)
    kinds = person_q() | platform_q() if _platform_origin(request) else person_q()
    user = live.filter(kinds, username=identifier).first()
    if user is not None or not identifier:
        return user
    by_email = Q(email__iexact=identifier) & ~Q(email="")
    user = live.filter(person_q(), by_email).first()
    if user is None and _platform_origin(request):
        user = live.filter(platform_q(), by_email).first()
    return user


def resolve_login(attrs, request):
    identifier = attrs.get("username", "")
    user = resolve_identifier(identifier, request)
    from apps.accounts.login_methods import password_login_enabled
    # The member password switch never locks out staff: they keep password + their
    # authenticator (#62). Unknown identities get the same refusal as members.
    closed = not password_login_enabled()
    if user is None or (closed and not is_platform(user) and not has_staff_role(user)):
        # Keep Django's password hashing work on unknown identities.
        User().set_password(attrs.get("password", ""))
        if closed:
            raise PermissionDenied("Password sign-in is not available on this deployment.")
        from django.contrib.auth.signals import user_login_failed
        user_login_failed.send(sender=__name__, credentials={"username": identifier}, request=request)
        raise AuthenticationFailed(_REFUSED, code="no_active_account")
    surface = "platform" if is_platform(user) else "member"
    try:
        assert_surface(user, surface, request)
    except AuthenticationFailed as exc:
        raise AuthenticationFailed(_REFUSED, code="no_active_account") from exc
    attrs["username"] = user.username
    return user, surface
