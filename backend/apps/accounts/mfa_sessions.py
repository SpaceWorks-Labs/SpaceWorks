"""Finish the original login after MFA without accepting client authority claims."""

from django.utils.translation import gettext
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.native_app_identity import eligible_registration_q
from apps.accounts import audit_events
from apps.accounts.models_devices import DeviceAttestationChallenge, DeviceGrant
from apps.accounts.serializers_device import DeviceGrantSerializer
from apps.accounts.services_device_tokens import issue_device_token_pair, assert_mobile_grant_creation_enabled
from apps.accounts.staff_identity import is_person
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.session_issuance import lock_session_user


def context(request, *, surface, device=None, login_method=None):
    from apps.accounts.social_nonces import request_origin
    origin = request_origin(request) if request is not None else ""
    if surface == "control":
        origin = request.build_absolute_uri("/").rstrip("/")
    return {"surface": surface, "origin": origin, **({"device": device} if device else {}),
            **({"login_method": login_method} if login_method else {})}


def device_context(challenge, verified, grant=None, *, login_method=None):
    return {"attestation_id": str(challenge.pk) if challenge else None,
            "subject_hash": audit_events.fingerprint(verified.subject) if verified else "",
            "attestation_metadata": verified.metadata if verified else {},
            "grant_id": str(grant.pk) if grant else None,
            "login_method": login_method}


def issue_session(user, data, request):
    from apps.accounts.serializers import user_payload
    # The MFA service already holds User; keep it first for native issuance too.
    user = lock_session_user(user)
    from apps.accounts.surface_policy import assert_surface, validate_account_token
    validate_account_token(user, data)
    surface = data["surface"]
    assert_surface(user, surface, request=request)
    if surface == "control":
        return {"mfa_version": str(user._mfa_verified_version)}
    device = data.get("device")
    if device:
        if not is_person(user):
            raise AuthenticationFailed(gettext("Device authorization is no longer active."))
        from apps.accounts.views_device import _reject_browser_headers
        _reject_browser_headers(request)
        assert_mobile_grant_creation_enabled()
        if device.get("grant_id"):
            grant = DeviceGrant.objects.select_for_update().filter(
                eligible_registration_q("registration__"),
                pk=device["grant_id"], user=user, status=DeviceGrant.Status.ACTIVE,
            ).first()
        else:
            from apps.accounts.services_device_grants import create_device_grant
            attestation = DeviceAttestationChallenge.objects.get(pk=device["attestation_id"])
            # A staff grant is a step-up: the fixed makerspace was chosen and checked when
            # the challenge started and is re-checked here, after the factor is proven.
            grant = create_device_grant(user, attestation,
                metadata=device.get("attestation_metadata", {}),
                subject_hash=device["subject_hash"], login_method=device.get("login_method"),
                staff_makerspace_id=device.get("staff_makerspace_id"), event_id=device.get("event_id"))
        if grant is None:
            raise AuthenticationFailed(gettext("Device authorization is no longer active."))
        access, refresh, _ = issue_device_token_pair(user, grant)
        from apps.accounts.native_event_grants import session_authority_for
        surface = session_authority_for(grant)
        request.device_grant = grant
        audit_events.record_auth_event(user, "auth.device_login_succeeded", target=user)
        return {"access": access, "refresh": refresh, "surface": surface,
                "user": user_payload(user, request=request, session_authority=surface), "device_grant": DeviceGrantSerializer(grant).data}
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = surface
    return {"access": str(refresh.access_token), "refresh": str(refresh), "surface": surface,
            "user": user_payload(user, request=request, session_authority=surface)}


def record_completed_sign_in(user, data, request, result):
    """S-B: a sign-in completed through a challenge remembers its device and network. Not
    the ``/control/`` step-up and not a settings enrolment (neither is a sign-in)."""
    device = data.get("device") or {}
    if data.get("surface") == "control" or device.get("purpose") == "settings_enroll":
        return
    from apps.accounts.login_risk import record_success
    method = device.get("login_method") or data.get("login_method") or "password"
    token = record_success(request, user, method=method, web=not device)
    if device and token:
        result["device_trust"] = token
