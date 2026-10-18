from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, PolymorphicProxySerializer
from apps.accounts.serializers_mfa import MFAChallengeResponseSerializer
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.native_app_identity import eligible_registration_q, matched_signing_identity
from apps.accounts import audit_events
from apps.accounts.attestation import (
    AttestationRejected, AttestationUnavailable,
    consume_attestation_challenge, create_challenge, verify_attestation,
)
from apps.accounts.login_methods import password_login_enabled
from apps.accounts.models import User
from apps.accounts.models_devices import DeviceGrant, NativeAppRegistration
from apps.accounts.serializers import user_payload
from apps.accounts.serializers_attestation import ATTESTATION_DESCRIPTION
from apps.accounts.serializers_device import (
    DeviceChallengeResponseSerializer, DeviceGrantSerializer,
    DeviceIdentitySerializer, DeviceLoginSerializer,
    DeviceLogoutResponseSerializer, DeviceRefreshResponseSerializer,
    DeviceRefreshSerializer, DeviceTokenResponseSerializer,
)
from apps.accounts.services_device_tokens import (
    rotate_device_refresh, issue_device_token_pair, assert_mobile_grant_creation_enabled,
)
from apps.accounts.services_tokens import revoke_device_grant
from apps.accounts.services_device_grants import (
    DeviceSuperadminNotSupported, assert_grant_user_allowed,
    audit_grant_refusal,
)
from apps.accounts.throttles import DeviceLoginThrottle, DeviceLoginUserThrottle
from apps.accounts.session_issuance import lock_session_user
from apps.hardware_requests.exceptions import ErrorSerializer


def _reject_browser_headers(request):
    if any(
        request.META.get(name)
        for name in ('HTTP_COOKIE', 'HTTP_ORIGIN', 'HTTP_REFERER')
    ):
        raise PermissionDenied("Browser credential transport is not allowed on device auth routes.")


class IsDeviceAccessToken(BasePermission):
    def has_permission(self, request, view):
        _reject_browser_headers(request)
        return bool(
            request.user and request.user.is_authenticated
            and request.user.account_kind in {"member", "staff"}
            and getattr(request, "device_grant", None)
            and request.auth and request.auth.get("token_type") == "access"
        )


class DeviceAttestationChallengeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "device_attestation_challenge"

    @extend_schema(tags=["Device auth"], auth=[], request=DeviceIdentitySerializer,
        description=ATTESTATION_DESCRIPTION,
        responses={200: DeviceChallengeResponseSerializer, 400: OpenApiResponse(ErrorSerializer), 429: OpenApiResponse(ErrorSerializer), 503: OpenApiResponse(ErrorSerializer)})
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceIdentitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            raw = create_challenge(**serializer.validated_data)
        except AttestationUnavailable:
            return Response({"detail": "Device attestation is unavailable.", "code": "attestation_unavailable"}, status=503)
        audit_events.record_auth_event(
            None,
            'auth.device_challenge_created',
            meta={
                'platform': serializer.validated_data['platform'],
                'environment': serializer.validated_data['environment'],
                'app_hash': audit_events.fingerprint(
                    serializer.validated_data['app_id']
                ),
            },
        )
        return Response({
            "challenge": raw,
            "expires_in": settings.DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS,
        })


def _consume_challenge(data):
    return consume_attestation_challenge(
        data["challenge"],
        platform=data["platform"],
        app_id=data["app_id"],
        environment=data["environment"],
    )


class DeviceLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DeviceLoginThrottle, DeviceLoginUserThrottle]

    @extend_schema(tags=["Device auth"], auth=[], request=DeviceLoginSerializer,
        description="Attested password sign-in. Staff accounts receive fixed-tenant native authority after password and MFA verification. New superadmin grants are refused with device_superadmin_not_supported (403). " + ATTESTATION_DESCRIPTION,
        responses={200: PolymorphicProxySerializer(component_name="DeviceLoginResult", serializers=[DeviceTokenResponseSerializer, MFAChallengeResponseSerializer], resource_type_field_name=None), 401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer), 503: OpenApiResponse(ErrorSerializer)})
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceLoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            _audit_login_failure(request.data, 'invalid_request')
            raise
        data = serializer.validated_data
        challenge = _consume_challenge(data)
        if challenge is None:
            _audit_login_failure(data, 'invalid_challenge')
            raise AuthenticationFailed("Invalid device credentials or attestation.")
        try:
            verified = verify_attestation(challenge, data["challenge"], data["attestation"])
        except AttestationUnavailable:
            _audit_login_failure(data, 'provider_unavailable')
            return Response({"detail": "Device attestation is unavailable.", "code": "attestation_unavailable"}, status=503)
        except AttestationRejected as exc:
            _audit_login_failure(data, 'attestation_rejected')
            raise AuthenticationFailed("Invalid device credentials or attestation.") from exc
        # MERGE-RECON(A): fold this native password adapter into services_device_login.
        user = _password_user(request, data)
        if (not user or user.is_tenant_dump_stub or user.retired_at is not None
                or user.deletion_requested_at is not None or user.access_status != "active"):
            _audit_login_failure(data, "invalid_credentials")
            raise AuthenticationFailed("Invalid device credentials or attestation.")
        try:
            assert_grant_user_allowed(user)
        except DeviceSuperadminNotSupported as exc:
            audit_grant_refusal(exc)
            raise
        if user.account_kind == "member" and not password_login_enabled():
            _audit_login_failure(data, "password_login_disabled")
            raise AuthenticationFailed("Invalid device credentials or attestation.")
        assert_mobile_grant_creation_enabled()
        from apps.accounts.surface_policy import assert_surface
        surface = "staff_api" if user.account_kind == "staff" else "member"
        assert_surface(user, surface, request)
        if user.account_kind == "staff" and challenge.registration.makerspace_id not in (None, user.staff_makerspace_id):
            raise AuthenticationFailed("Invalid device credentials or attestation.")
        from apps.accounts.mfa_policy import needs_challenge
        from apps.accounts.mfa_challenges import start
        from apps.accounts.mfa_sessions import context, device_context
        if user.account_kind == "staff" or needs_challenge(user):
            response = Response(start(user, context=context(request, surface=surface,
                device=device_context(challenge, verified, login_method="password"))))
            response["Cache-Control"] = "no-store"
            return response
        try:
            with transaction.atomic():
                from apps.accounts.credential_locks import lock_token_issuance
                lock_token_issuance(user)
                user = lock_session_user(user)
                registration = NativeAppRegistration.objects.select_for_update().filter(
                    eligible_registration_q(), pk=challenge.registration_id,
                    platform=challenge.platform, app_id=challenge.app_id,
                    environment=challenge.environment).first()
                if registration is None:
                    raise _RegistrationNotApproved()
                now = timezone.now()
                grant = DeviceGrant.objects.create(
                    registration=registration, user=user, authority=user.account_kind,
                    platform=challenge.platform, app_id=challenge.app_id, environment=challenge.environment,
                    signing_identity=matched_signing_identity(challenge, verified.metadata),
                    attestation_subject_fingerprint=audit_events.fingerprint(verified.subject),
                    attestation_key_id=verified.metadata.get("key_id"),
                    attestation_public_key=verified.metadata.get("public_key"),
                    attested_at=now, last_used_at=now)
                access, refresh, _ = issue_device_token_pair(user, grant)
        except _RegistrationNotApproved as exc:
            _audit_login_failure(data, "registration_not_approved")
            raise AuthenticationFailed("Invalid device credentials or attestation.") from exc
        request.device_grant = grant
        audit_events.record_auth_event(user, "auth.device_login_succeeded", target=user,
            meta={"grant_hash": audit_events.fingerprint(grant.pk)})
        return Response({"access": access, "refresh": refresh,
                         "user": user_payload(user, request=request, session_authority=surface),
                         "device_grant": DeviceGrantSerializer(grant).data})


class DeviceRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "device_refresh"

    @extend_schema(tags=["Device auth"], auth=[], request=DeviceRefreshSerializer,
        responses={200: DeviceRefreshResponseSerializer, 400: OpenApiResponse(ErrorSerializer), 401: OpenApiResponse(ErrorSerializer), 429: OpenApiResponse(ErrorSerializer)})
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access, refresh, grant, user = rotate_device_refresh(serializer.validated_data["refresh"])
        audit_events.record_auth_event(
            user,
            'auth.device_refresh_rotated',
            target=user,
            meta={'grant_hash': audit_events.fingerprint(grant.pk)},
        )
        return Response({"access": access, "refresh": refresh, "device_grant": DeviceGrantSerializer(grant).data})


class DeviceLogoutView(APIView):
    permission_classes = [IsAuthenticated, IsDeviceAccessToken]

    @extend_schema(tags=["Device auth"], request=None, responses={200: DeviceLogoutResponseSerializer, 401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer)})
    def post(self, request):
        _reject_browser_headers(request)
        revoke_device_grant(request.device_grant)
        audit_events.record_auth_event(request.user, "auth.device_logout", target=request.user,
            meta={"grant_hash": audit_events.fingerprint(request.device_grant.pk)})
        return Response({"detail": "Device logged out."})


class DeviceGrantListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Device auth"], request=None, responses={200: DeviceGrantSerializer(many=True), 401: OpenApiResponse(ErrorSerializer)})
    def get(self, request):
        from apps.accounts.surface_policy import assert_surface
        assert_surface(request.user, "staff_api" if request.user.account_kind == "staff" else "member")
        grants = DeviceGrant.objects.filter(user=request.user).order_by("-last_used_at")
        return Response(DeviceGrantSerializer(grants, many=True).data)


class DeviceGrantDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Device auth"], request=None, responses={204: None, 401: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)})
    def delete(self, request, grant_id):
        from apps.accounts.surface_policy import assert_surface
        assert_surface(request.user, "staff_api" if request.user.account_kind == "staff" else "member")
        grant = DeviceGrant.objects.filter(pk=grant_id, user=request.user).first()
        if grant is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        revoke_device_grant(grant)
        audit_events.record_auth_event(request.user, "auth.device_grant_revoked", target=request.user,
            meta={"grant_hash": audit_events.fingerprint(grant.pk)})
        return Response(status=status.HTTP_204_NO_CONTENT)


def _audit_login_failure(data, reason):
    audit_events.record_auth_event(
        None,
        'auth.device_login_failed',
        meta={
            'username_hash': audit_events.fingerprint(
                (data or {}).get('username')
            ),
            'reason': reason,
        },
    )


class _RegistrationNotApproved(Exception):
    pass


def _password_user(request, data):
    # Explicit staff usernames avoid resolving shared contacts across account kinds.
    # Email fallback is confined to the member namespace; staff usernames are global.
    with transaction.atomic():
        rows = User.objects.select_for_update(no_key=True).filter(is_active=True, retired_at__isnull=True)
        user = rows.filter(username=data["username"]).first()
        if user is None:
            user = rows.filter(account_kind="member", email__iexact=data["username"]).exclude(email="").first()
        if user is None:
            User().set_password(data["password"])
            from django.contrib.auth.signals import user_login_failed
            user_login_failed.send(sender=__name__, credentials={"username": data["username"]}, request=request)
            return None
        authenticated = authenticate(request=request, username=user.username, password=data["password"])
        return authenticated if authenticated is not None and authenticated.pk == user.pk else None
