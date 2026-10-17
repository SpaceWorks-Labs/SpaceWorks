"""Resolve native password credentials only inside the member identity namespace."""

from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_login_failed
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

from apps.accounts import audit_events
from apps.accounts.models_devices import DeviceGrant, NativeAppRegistration
from apps.accounts.serializers_device import DeviceGrantSerializer
from apps.accounts.serializers_payload import user_payload
from apps.accounts.services_device_tokens import assert_mobile_grant_creation_enabled, issue_device_token_pair

from apps.accounts.models import User


def authenticate_member(request, identifier, password):
    users = User.objects.select_for_update(no_key=True).filter(
        account_kind="member", retired_at__isnull=True, is_active=True)
    user = users.filter(username=identifier).first()
    if user is None:
        matches = users.filter(email__iexact=identifier).exclude(email="")
        user = matches.first() if matches.count() == 1 else None
    if user is None:
        User().set_password(password)
        user_login_failed.send(sender=__name__, credentials={"username": identifier}, request=request)
        return None
    authenticated = authenticate(request=request, username=user.username, password=password)
    return authenticated if authenticated is not None and authenticated.pk == user.pk else None


class DevicePasswordRejected(AuthenticationFailed):
    def __init__(self, reason):
        self.reason = reason
        super().__init__("Invalid device credentials or attestation.")


def password_login(request, data, challenge, verified):
    """Hold the account lock from password verification through session issuance.

    Attestation was already checked outside this transaction, so provider latency
    cannot keep a password reset waiting on the member row.
    """
    refusal = None
    with transaction.atomic():
        try:
            result = _password_login_locked(request, data, challenge, verified)
        except DevicePasswordRejected as exc:
            # Django's failure signal updates the axes counter in this transaction.
            # Commit that accounting before returning the generic credential error.
            refusal = exc
    if refusal is not None:
        raise refusal
    return result


def _password_login_locked(request, data, challenge, verified):
    user = authenticate_member(request, data["username"], data["password"])
    if (not user or user.account_kind != "member" or user.retired_at is not None
            or user.is_tenant_dump_stub or user.access_status != User.AccessStatus.ACTIVE):
        raise DevicePasswordRejected("invalid_credentials")
    assert_mobile_grant_creation_enabled()
    from apps.accounts.mfa_policy import needs_challenge
    from apps.accounts.mfa_challenges import start
    from apps.accounts.mfa_sessions import context, device_context
    if needs_challenge(user):
        response = Response(start(user, context=context(request, surface="member",
            device=device_context(challenge, verified))))
        response["Cache-Control"] = "no-store"
        return response
    registration = NativeAppRegistration.objects.select_for_update().filter(
        pk=challenge.registration_id, status=NativeAppRegistration.Status.APPROVED,
    ).first()
    if registration is None:
        raise DevicePasswordRejected("registration_not_approved")
    now = timezone.now()
    grant = DeviceGrant.objects.create(
        registration=registration, user=user, platform=challenge.platform, app_id=challenge.app_id,
        signing_identity=challenge.signing_identity, environment=challenge.environment,
        attestation_subject_fingerprint=audit_events.fingerprint(verified.subject),
        attested_at=now, last_used_at=now,
    )
    access, refresh, _ = issue_device_token_pair(user, grant)
    request.device_grant = grant
    audit_events.record_auth_event(user, "auth.device_login_succeeded", target=user,
        meta={"grant_hash": audit_events.fingerprint(grant.pk)})
    return Response({"access": access, "refresh": refresh,
        "user": user_payload(user, request=request),
        "device_grant": DeviceGrantSerializer(grant).data})
