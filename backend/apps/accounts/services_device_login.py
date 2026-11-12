"""Attested password sign-in for a person: member authority, or a staff step-up fixed to
one makerspace (``authority=staff`` with that makerspace's slug, always behind MFA)."""

from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_login_failed
from django.db import transaction
from django.db.models import Q
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
from apps.accounts.staff_identity import has_staff_role, person_q


class DevicePasswordRejected(AuthenticationFailed):
    def __init__(self, reason):
        self.reason = reason
        super().__init__("Invalid device credentials or attestation.")


def authenticate_native(request, identifier, password):
    # Persons only (the superadmin never holds a device grant); lock User alone. Joining a
    # makerspace must never acquire its lock after User in an issuance path.
    users = User.objects.select_for_update(of=("self",), no_key=True).filter(
        person_q(), retired_at__isnull=True, merged_into__isnull=True, is_active=True,
    )
    user = users.filter(username=identifier).first()
    if user is None:
        user = users.filter(Q(email__iexact=identifier) & ~Q(email="")).first()
    if user is None:
        User().set_password(password)
        user_login_failed.send(sender=__name__, credentials={"username": identifier}, request=request)
        return None
    authenticated = authenticate(request=request, username=user.username, password=password)
    return authenticated if authenticated is not None and authenticated.pk == user.pk else None


def staff_makerspace_for(slug):
    """The servable makerspace a staff step-up names, or None (read before User is locked)."""
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_queryset

    return servable_queryset(Makerspace.objects.filter(slug=slug)).values_list("pk", flat=True).first() if slug else None


def password_login(request, data, challenge, verified):
    """Keep User locked from password verification through challenge or token minting."""
    refusal = None
    staff_space = staff_makerspace_for(data.get("makerspace")) if data["authority"] == "staff" else None
    with transaction.atomic():
        try:
            result = _password_login_locked(request, data, challenge, verified, staff_space)
        except DevicePasswordRejected as exc:
            # Commit Django/axes failed-password accounting before returning the error.
            refusal = exc
    if refusal is not None:
        raise refusal
    return result


def _password_login_locked(request, data, challenge, verified, staff_space):
    user = authenticate_native(request, data["username"], data["password"])
    from apps.accounts.restricted_admission import state_may_sign_in
    if (not user or user.is_tenant_dump_stub or user.retired_at is not None
            or user.deletion_requested_at is not None or not state_may_sign_in(user)):
        raise DevicePasswordRejected("invalid_credentials")
    assert_grant_user_allowed(user)
    staff = data["authority"] == "staff"
    # Decision 361: a restricted or suspended person gets a MEMBER grant only, never staff authority.
    if staff and (staff_space is None or user.access_status != "active" or not has_staff_role(user, staff_space)):
        raise DevicePasswordRejected("staff_access_required")
    # Staff keep password sign-in when the deployment turned it off for members (#62).
    if not password_login_enabled() and not has_staff_role(user):
        raise DevicePasswordRejected("password_login_disabled")
    assert_mobile_grant_creation_enabled()
    from apps.accounts.surface_policy import assert_surface
    assert_surface(user, "member", request)
    if staff and challenge.registration.makerspace_id not in (None, staff_space):
        raise DevicePasswordRejected("registration_not_approved")
    from apps.accounts.mfa_policy import needs_challenge
    from apps.accounts.mfa_challenges import start
    from apps.accounts.mfa_sessions import context, device_context
    if staff or needs_challenge(user):
        device = device_context(challenge, verified, login_method="password")
        if staff:
            device["staff_makerspace_id"] = staff_space
        response = Response(start(user, context=context(request, surface="member", device=device)))
        response["Cache-Control"] = "no-store"
        return response
    # S-B: an unusual sign-in by someone without a factor proves the mailbox first.
    from apps.accounts.login_risk import record_success, step_up
    risk = step_up(request, user, method="password", context=context(
        request, surface="member", device=device_context(challenge, verified, login_method="password")))
    if risk is not None:
        response = Response(risk)
        response["Cache-Control"] = "no-store"
        return response
    try:
        access, refresh, grant = issue_first_device_session(user, challenge, verified, login_method="password")
    except DeviceGrantCreationRetryRequired as exc:
        raise DevicePasswordRejected("registration_not_approved") from exc
    request.device_grant = grant
    return Response({"access": access, "refresh": refresh,
        "user": user_payload(user, request=request, session_authority="member"),
        "device_grant": DeviceGrantSerializer(grant).data,
        "device_trust": record_success(request, user, method="password", web=False)})
