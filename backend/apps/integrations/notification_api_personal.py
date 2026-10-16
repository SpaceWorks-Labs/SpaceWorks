from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.notifications.models_preferences import NotificationPreference
from .notification_api_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from .notification_api_access import contract_space
from .notification_api_serializers import (
    ChallengeSerializer, ChallengeStartSerializer, EndpointSerializer, EndpointPageSerializer,
    PreferencesSerializer, ProofVerifySerializer, RevokedSerializer,
)
from .notification_resolution import policy_rows


class ProofThrottle(UserRateThrottle):
    rate = "20/hour"
    scope = "notification_endpoint_proof"


class EndpointListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal notification contract"], parameters=[OpenApiParameter("page", int)],
                   responses={200: EndpointPageSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id)
        rows = policy_rows(NotificationEndpoint, space).filter(user=request.user)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows.order_by("-created_at", "-pk"), request, view=self)
        return paginator.get_paginated_response(EndpointSerializer(page, many=True).data)


class EndpointStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProofThrottle]

    @extend_schema(tags=["Personal notification contract"], request=ChallengeStartSerializer,
                   responses={201: ChallengeSerializer, **errors(400, 401, 403, 404, 429, 423, 503)})
    def post(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id)
        serializer = ChallengeStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        config = get_object_or_404(policy_rows(ChannelConfiguration, space), channel=data["channel"])
        from .notification_proofs import start
        challenge, result = start(request.user, config, data["consent_version"], phone_number=data.get("phone_number", ""))
        # Providers may return only the documented fields, never their raw response.
        return Response(ChallengeSerializer({"challenge_id": challenge.pk, "expires_at": challenge.expires_at,
            **{key: result[key] for key in ("connect_url", "instructions") if key in result}}).data, status=201)


class EndpointVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProofThrottle]

    @extend_schema(tags=["Personal notification contract"], request=ProofVerifySerializer,
                   responses={200: EndpointSerializer, **errors(400, 401, 403, 404, 429, 423, 503)})
    def post(self, request, makerspace_id, challenge_id):
        space = contract_space(request.user, makerspace_id)
        serializer = ProofVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = get_object_or_404(policy_rows(NotificationEndpointChallenge, space), pk=challenge_id, user=request.user)
        if challenge.consumed_at and challenge.endpoint_id:
            endpoint = challenge.endpoint
            config = challenge.configuration
            if (endpoint.revoked_at or endpoint.verification_state != "verified"
                    or endpoint.integration_generation != config.generation):
                raise ValidationError({"proof": "This connection is no longer valid."})
            # A signed inbound proof may already have consumed the challenge. The
            # browser can acknowledge its own proven result without supplying IDs.
            return Response(EndpointSerializer(endpoint).data)
        from .notification_proofs import verified_callback
        endpoint = verified_callback(challenge.configuration, request, expected_user_id=request.user.pk,
                                     expected_challenge_id=challenge.pk)
        return Response(EndpointSerializer(endpoint).data)


class EndpointRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Personal notification contract"], request=None,
                   responses={200: RevokedSerializer, **errors(400, 401, 403, 404, 423, 503)})
    def delete(self, request, makerspace_id, pk):
        space = contract_space(request.user, makerspace_id)
        endpoint = get_object_or_404(policy_rows(NotificationEndpoint, space), pk=pk, user=request.user)
        from .notification_proofs import revoke
        with tenant_write(space.pk), transaction.atomic():
            revoke(endpoint, actor=request.user)
        return Response({"revoked": True})


class PersonalSelectionView(APIView):
    permission_classes = [IsAuthenticated]

    def response(self, space, user):
        from types import SimpleNamespace
        from .notification_enums import NotificationFeature
        from .notification_resolution import selected_policy
        from .notification_availability import available_channels
        preferences = []
        for category in NotificationFeature.values:
            channels, fallback = selected_policy(SimpleNamespace(makerspace=space, recipient=user,
                recipient_id=user.pk, makerspace_id=space.pk, feature=category))
            preferences.append({"category": category, "channels": channels, "email_fallback": fallback,
                                "available_channels": available_channels(space, category)})
        return Response({"preferences": preferences})

    @extend_schema(tags=["Personal notification contract"], responses={200: PreferencesSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        return self.response(contract_space(request.user, makerspace_id), request.user)

    @extend_schema(tags=["Personal notification contract"], request=PreferencesSerializer,
                   responses={200: PreferencesSerializer, **errors(400, 401, 403, 404, 423, 503)})
    def put(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id)
        serializer = PreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preferences = serializer.validated_data["preferences"]
        from .notification_availability import available_channels
        for preference in preferences:
            if set(preference["channels"]) - set(available_channels(space, preference["category"])):
                raise ValidationError({"channels": "Choose channels enabled by this makerspace for the category."})
        with tenant_write(space.pk), transaction.atomic():
            # Complete replacement; omitted categories resume their documented defaults.
            policy_rows(NotificationPreference, space).filter(user=request.user).delete()
            for preference in preferences:
                NotificationPreference.objects.create(makerspace=space, user=request.user, **preference)
            audit.record(request.user, "notification.channel_preferences_updated", makerspace=space,
                         target=space, meta={"categories": [p["category"] for p in preferences]})
        return self.response(space, request.user)
