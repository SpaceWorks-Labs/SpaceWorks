"""Attested password login for immutable member and fixed-tenant staff accounts."""

from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_login_failed
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

from apps.accounts.login_methods import password_login_enabled
from apps.accounts.models import User
from apps.accounts.serializers_device import DeviceGrantSerializer
from apps.accounts.serializers_payload import user_payload
from apps.accounts.services_device_grants import (
    DeviceGrantCreationRetryRequired, assert_grant_user_allowed, issue_first_device_session,
)
from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled


class DevicePasswordRejected(AuthenticationFailed):
    def __init__(self, reason):
        self.reason = reason
        super().__init__("Invalid device credentials or attestation.")


def authenticate_native(request, identifier, password, *, context="member", makerspace=None):
    # Resolve only the explicit account namespace, then lock User alone. Joining
    # the staff tenant must never acquire its lock after User in an issuance path.
    users = User.objects.select_for_update(of=("self",), no_key=True).filter(
        account_kind=context, retired_at__isnull=True, is_active=True,
    )
    if context == "staff":
        users = users.filter(staff_makerspace__slug=makerspace)
    user = users.filter(username=identifier).first()
    if user is None:
        user = users.filter(email__iexact=identifier).exclude(email="").first()
    if user is None:
        User().set_password(password)
        user_login_failed.send(sender=__name__, credentials={"username": identifier}, request=request)
        return None
    authenticated = authenticate(request=request, username=user.username, password=password)
    return authenticated if authenticated is not None and authenticated.pk == user.pk else None


def password_login(request, data, challenge, verified):
    """Keep User locked from password verification through challenge or token minting."""
    refusal = None
    with transaction.atomic():
        try:
            result = _password_login_locked(request, data, challenge, verified)
        except DevicePasswordRejected as exc:
            # Commit Django/axes failed-password accounting before returning the error.
            refusal = exc
    if refusal is not None:
        raise refusal
    return result


def _password_login_locked(request, data, challenge, verified):
    user = authenticate_native(request, data["username"], data["password"],
                               context=data["context"], makerspace=data.get("makerspace"))
    if (not user or user.is_tenant_dump_stub or user.retired_at is not None
            or user.deletion_requested_at is not None or user.access_status != "active"):
        raise DevicePasswordRejected("invalid_credentials")
    assert_grant_user_allowed(user)
    if user.account_kind == "member" and not password_login_enabled():
        raise DevicePasswordRejected("password_login_disabled")
    assert_mobile_grant_creation_enabled()
    from apps.accounts.surface_policy import assert_surface
    surface = "staff_api" if user.account_kind == "staff" else "member"
    assert_surface(user, surface, request)
    if user.account_kind == "staff" and challenge.registration.makerspace_id not in (None, user.staff_makerspace_id):
        raise DevicePasswordRejected("registration_not_approved")
    from apps.accounts.mfa_policy import needs_challenge
    from apps.accounts.mfa_challenges import start
    from apps.accounts.mfa_sessions import context, device_context
    if user.account_kind == "staff" or needs_challenge(user):
        response = Response(start(user, context=context(request, surface=surface,
            device=device_context(challenge, verified, login_method="password"))))
        response["Cache-Control"] = "no-store"
        return response
    try:
        access, refresh, grant = issue_first_device_session(user, challenge, verified, login_method="password")
    except DeviceGrantCreationRetryRequired as exc:
        raise DevicePasswordRejected("registration_not_approved") from exc
    request.device_grant = grant
    return Response({"access": access, "refresh": refresh,
        "user": user_payload(user, request=request, session_authority=surface),
        "device_grant": DeviceGrantSerializer(grant).data})
