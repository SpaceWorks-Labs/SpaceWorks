"""Finish the original login after MFA without accepting client authority claims."""

from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from apps.accounts.native_app_identity import eligible_registration_q, matched_signing_identity
from apps.accounts import audit_events
from apps.accounts.models_devices import DeviceAttestationChallenge, DeviceGrant, NativeAppRegistration
from apps.accounts.serializers_device import DeviceGrantSerializer
from apps.accounts.services_device_tokens import issue_device_token_pair, assert_mobile_grant_creation_enabled
from apps.accounts.services_social_login import assert_staff_authority
from apps.accounts.services_device_grants import assert_grant_user_allowed
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.accounts.session_issuance import lock_session_user


def context(request, *, surface, staff_scope=None, device=None):
    from apps.accounts.social_nonces import request_origin
    origin = request_origin(request) if request is not None else ""
    if surface == "control":
        origin = request.build_absolute_uri("/").rstrip("/")
    return {"surface": surface, "staff_scope": staff_scope,
            "origin": origin, **({"device": device} if device else {})}


def device_context(challenge, verified, grant=None, *, login_method=None):
    return {"attestation_id": str(challenge.pk) if challenge else None,
            "subject_hash": audit_events.fingerprint(verified.subject) if verified else "",
            "attestation_metadata": verified.metadata if verified else {},
            "grant_id": str(grant.pk) if grant else None,
            "login_method": login_method}


def issue_session(user, data, request):
    from apps.accounts.serializers import user_payload
    # The MFA service already holds User; keep it first for native issuance too.
    from apps.accounts.credential_locks import lock_token_issuance
    lock_token_issuance(user)
    user = lock_session_user(user)
    from apps.accounts.surface_policy import assert_surface, validate_account_token
    validate_account_token(user, data)
    surface = data["surface"]
    assert_surface(user, surface, request=request)
    if surface == "control":
        return {"mfa_version": str(user._mfa_verified_version)}
    if surface in ("staff", "staff_api", "delegated"):
        from apps.accounts.services_social_identity import SocialResolutionError
        try:
            assert_staff_authority(user, request)
        except SocialResolutionError as exc:
            raise PermissionDenied("Staff access is required.") from exc
    device = data.get("device")
    if device:
        if user.account_kind not in {"member", "staff"} or (user.account_kind == "staff" and device.get("login_method") != "password"):
            raise AuthenticationFailed("Device authorization is no longer active.")
        from apps.accounts.views_device import _reject_browser_headers
        _reject_browser_headers(request)
        assert_mobile_grant_creation_enabled()
        if device.get("grant_id"):
            grant = DeviceGrant.objects.select_for_update().filter(
                eligible_registration_q("registration__"),
                pk=device["grant_id"], user=user, status=DeviceGrant.Status.ACTIVE,
            ).first()
        else:
            assert_grant_user_allowed(user)
            attestation = DeviceAttestationChallenge.objects.get(pk=device["attestation_id"])
            registration = NativeAppRegistration.objects.select_for_update().filter(
                eligible_registration_q(), pk=attestation.registration_id,
                platform=attestation.platform, app_id=attestation.app_id, environment=attestation.environment,
            ).first()
            grant = None
            if registration:
                grant = DeviceGrant.objects.create(
                    registration=registration, user=user, platform=attestation.platform,
                    authority=user.account_kind,
                    app_id=attestation.app_id, environment=attestation.environment,
                    signing_identity=matched_signing_identity(attestation, device.get("attestation_metadata", {})),
                    attestation_subject_fingerprint=device["subject_hash"],
                    attestation_key_id=device.get("attestation_metadata", {}).get("key_id"),
                    attestation_public_key=device.get("attestation_metadata", {}).get("public_key"),
                    attested_at=timezone.now(), last_used_at=timezone.now(),
                )
        if grant is None:
            raise AuthenticationFailed("Device authorization is no longer active.")
        if user.account_kind == "staff" and grant.registration.makerspace_id not in (None, user.staff_makerspace_id):
            raise AuthenticationFailed("Device authorization is no longer active.")
        access, refresh, _ = issue_device_token_pair(user, grant)
        surface = "native_staff" if grant.authority == DeviceGrant.Authority.STAFF else "member"
        request.device_grant = grant
        audit_events.record_auth_event(user, "auth.device_login_succeeded", target=user)
        return {"access": access, "refresh": refresh, "surface": surface,
                "user": user_payload(user, request=request, session_authority=surface), "device_grant": DeviceGrantSerializer(grant).data}
    refresh = SpaceWorksRefreshToken.for_user(user)
    refresh["surface"] = surface
    if surface == "staff":
        refresh["staff_scope"] = data.get("staff_scope") or "platform"
    return {"access": str(refresh.access_token), "refresh": str(refresh), "surface": surface,
            "user": user_payload(user, request=request, session_authority=surface)}
