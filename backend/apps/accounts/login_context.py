"""Validate the password door before authenticating a username in its namespace."""

from django.conf import settings
from django.db.models import Q
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.accounts.surface_policy import assert_surface


def resolve_login(attrs, request):
    surface = attrs.pop("surface", None)
    kind = attrs.pop("context", None) or ("staff" if surface == "staff" else "member")
    slug = attrs.pop("makerspace", None)
    if kind == "staff" and not slug:
        raise ValidationError({"makerspace": "This field is required for staff sign-in."})
    if kind != "staff" and slug:
        raise ValidationError({"makerspace": "Use a makerspace only for staff sign-in."})
    if surface and ((kind == "member" and surface not in {"member", "delegated"})
                    or (kind != "member" and surface != "staff")):
        raise AuthenticationFailed("No active account found with the given credentials")
    from apps.accounts.login_methods import password_login_enabled
    if kind == "member" and not password_login_enabled():
        raise PermissionDenied("Password sign-in is not available on this deployment.")
    rows = User.objects.filter(account_kind=kind, is_active=True, retired_at__isnull=True)
    if kind == "staff":
        rows = rows.filter(staff_makerspace__slug=slug)
    if kind == "platform":
        from apps.accounts.social_nonces import request_origin
        if request is None or request_origin(request) not in settings.PLATFORM_STAFF_ORIGINS:
            raise AuthenticationFailed("No active account found with the given credentials")
    identifier = attrs.get("username", "")
    # Prefer an exact username inside this namespace, then a unique email match.
    user = rows.filter(username=identifier).first()
    if user is None:
        user = rows.filter(Q(email__iexact=identifier) & ~Q(email="")).first()
    if user is None:
        # Keep Django's password hashing work on unknown identities.
        User().set_password(attrs.get("password", ""))
        from django.contrib.auth.signals import user_login_failed
        user_login_failed.send(sender=__name__, credentials={"username": identifier}, request=request)
        raise AuthenticationFailed("No active account found with the given credentials")
    resolved_surface = ({"staff": "staff_api", "platform": "platform"}.get(kind)
                        or surface or "member")
    try:
        assert_surface(user, resolved_surface, request)
    except AuthenticationFailed as exc:
        raise AuthenticationFailed("No active account found with the given credentials") from exc
    attrs["username"] = user.username
    return user, resolved_surface
