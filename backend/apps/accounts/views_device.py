from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, PolymorphicProxySerializer
from apps.accounts.serializers_mfa import MFAChallengeResponseSerializer
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import audit_events
from apps.accounts.attestation import (
    AttestationRejected, AttestationUnavailable,
    consume_attestation_challenge, create_challenge, verify_attestation,
)
from apps.accounts.models_devices import DeviceGrant
from apps.accounts.serializers_attestation import ATTESTATION_DESCRIPTION
from apps.accounts.serializers_device import (
    DeviceChallengeResponseSerializer, DeviceGrantPageSerializer, DeviceGrantSerializer,
    DeviceIdentitySerializer, DeviceLoginSerializer,
    DeviceLogoutResponseSerializer, DeviceRefreshResponseSerializer,
    DeviceRefreshSerializer, DeviceTokenResponseSerializer,
)
from apps.accounts.services_device_tokens import (
    rotate_device_refresh,
)
from apps.accounts.services_tokens import revoke_device_grant
from apps.accounts.services_device_grants import (
    DeviceSuperadminNotSupported,
    audit_grant_refusal,
)
from apps.accounts.throttles import DeviceLoginThrottle, DeviceLoginUserThrottle
from apps.accounts.native_app_version import assert_supported
from apps.accounts.staff_identity import is_person
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
            and is_person(request.user)
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
        description="Attested password sign-in for a person (one account per person; there is no account context). authority=member (default) issues a member grant. authority=staff with a makerspace slug is a step-up fixed to that makerspace: the person must hold a staff role there and always passes the authenticator (or enrols), and the grant is attested. A platform account is refused with device_superadmin_not_supported (403). An app older than MIN_NATIVE_APP_VERSION_* is refused with 426 native_app_update_required. " + ATTESTATION_DESCRIPTION,
        responses={200: PolymorphicProxySerializer(component_name="DeviceLoginResult", serializers=[DeviceTokenResponseSerializer, MFAChallengeResponseSerializer], resource_type_field_name=None), 401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer), 426: OpenApiResponse(ErrorSerializer, description="native_app_update_required"), 503: OpenApiResponse(ErrorSerializer)})
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceLoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            _audit_login_failure(request.data, 'invalid_request')
            raise
        data = serializer.validated_data
        assert_supported(data["platform"], data.get("app_version"))
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
        from apps.accounts.services_device_login import DevicePasswordRejected, password_login
        try:
            return password_login(request, data, challenge, verified)
        except DevicePasswordRejected as exc:
            _audit_login_failure(data, exc.reason)
            raise
        except DeviceSuperadminNotSupported as exc:
            audit_grant_refusal(exc)
            raise



class DeviceRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "device_refresh"

    @extend_schema(tags=["Device auth"], auth=[], request=DeviceRefreshSerializer,
        description="Rotate a device refresh token. A family minted before the deployment's current authentication generation (for example before the release-2 account cutover) is revoked and refused with 401 session_revoked. An app older than MIN_NATIVE_APP_VERSION_* is refused with 426 native_app_update_required before anything rotates. A staff grant whose staff role is gone is revoked.",
        responses={200: DeviceRefreshResponseSerializer, 400: OpenApiResponse(ErrorSerializer), 401: OpenApiResponse(ErrorSerializer, description="Invalid, replayed or revoked refresh; session_revoked after a generation change."), 426: OpenApiResponse(ErrorSerializer, description="native_app_update_required"), 429: OpenApiResponse(ErrorSerializer)})
    def post(self, request):
        _reject_browser_headers(request)
        serializer = DeviceRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access, refresh, grant, user = rotate_device_refresh(
            serializer.validated_data["refresh"], app_version=serializer.validated_data.get("app_version"))
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

    # The operation id stays "_list" now that the response is a page object, so generated
    # client method names do not change.
    @extend_schema(tags=["Device auth"], operation_id="api_v1_auth_device_grants_list", request=None,
                   parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY,
                                                description="Page number (24 rows per page).")],
                   responses={200: DeviceGrantPageSerializer, 401: OpenApiResponse(ErrorSerializer)})
    def get(self, request):
        from apps.accounts.surface_policy import assert_surface
        assert_surface(request.user, "member")
        # The tiebreakers keep page boundaries stable when grants share a last-used time.
        grants = DeviceGrant.objects.filter(user=request.user).order_by("-last_used_at", "-created_at", "pk")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(grants, request, view=self)
        return paginator.get_paginated_response(DeviceGrantSerializer(page, many=True).data)


class DeviceGrantDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Device auth"], request=None, responses={204: None, 401: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)})
    def delete(self, request, grant_id):
        from apps.accounts.surface_policy import assert_surface
        assert_surface(request.user, "member")
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
