"""Public programme pages and the join request, plus accepting an emailed invite.

Lists and pages are anonymous reads (noindex is set by the SPA); joining needs a
signed-in active account and is throttled (`id_join` 10/min, photo uploads 12/hour).
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.openapi import PUBLIC_API_AUTH_PARAMETERS
from apps.openapi_errors import errors
from apps.card_designs.serializers_openapi import PhotoUploadSerializer

from .serializers_openapi import (
    InviteAcceptResultSerializer, JoinPhotoRequestSerializer, JoinResultSerializer, PrefillSerializer,
    IdProgrammeDetailSerializer,
)

from . import invites, join
from .serializers import JoinSerializer, PublicProgrammeSerializer

TAGS = ["Public ID programmes"]


def _state(user, programme):
    if not user.is_authenticated:
        return "signed_out"
    card = programme.cards.filter(user=user).first()
    if card is None:
        return "open" if programme.registration_open else "closed"
    return {"pending": "waiting", "approved": "approved", "rejected": "not_approved", "revoked": "revoked"}[card.status]


class PublicProgrammeListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=TAGS, summary="Open ID programmes of an organisation", parameters=PUBLIC_API_AUTH_PARAMETERS,
                   request=None, responses={200: PublicProgrammeSerializer(many=True), **errors(404)})
    def get(self, request, slug):
        rows = [row for row in join.open_programmes(slug) if row.registration_open]
        return Response(PublicProgrammeSerializer(rows, many=True).data)


class PublicProgrammeDetailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=TAGS, summary="One programme's join page, with my request state when signed in",
                   parameters=PUBLIC_API_AUTH_PARAMETERS, request=None,
                   responses={200: IdProgrammeDetailSerializer, **errors(404)})
    def get(self, request, slug, programme_slug):
        programme = join.programme_by_slug(slug, programme_slug)
        return Response({**PublicProgrammeSerializer(programme).data, "state": _state(request.user, programme)})


class PublicProgrammeJoinView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "id_join"

    @extend_schema(tags=TAGS, summary="Ask to join (the email comes from your account)", request=JoinSerializer,
                   parameters=PUBLIC_API_AUTH_PARAMETERS,
                   responses={201: JoinResultSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, slug, programme_slug):
        programme = join.programme_by_slug(slug, programme_slug)
        data = JoinSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        card = join.join(request.user, programme, answers=values.get("answers") or {},
                         photo_object_key=values.get("photo_object_key", ""), photo_consent=values["photo_consent"])
        return Response({"state": _state(request.user, programme), "card_id": card.pk}, status=status.HTTP_201_CREATED)


class PublicProgrammePrefillView(APIView):
    """Opt-in Saved-details prefill for the join form: the owner's own values, never stored."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "id_join"

    @extend_schema(tags=TAGS, summary="Fill the join form from my Saved details (only when I ask)",
                   parameters=PUBLIC_API_AUTH_PARAMETERS, request=None,
                   responses={200: PrefillSerializer, **errors(401, 403, 404, 429)})
    def get(self, request, slug, programme_slug):
        from .prefill import values_for
        programme = join.programme_by_slug(slug, programme_slug)
        join.require_joiner(request.user)
        response = Response({"values": values_for(request.user, programme)})
        response["Cache-Control"] = "private, no-store"
        return response


class PublicProgrammeJoinPhotoView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "id_join_upload"

    @extend_schema(tags=TAGS, summary="Start a photo upload for a join request (staging presign only)",
                   parameters=PUBLIC_API_AUTH_PARAMETERS,
                   request=JoinPhotoRequestSerializer,
                   responses={201: PhotoUploadSerializer, **errors(400, 401, 404, 429, 503)})
    def post(self, request, slug, programme_slug):
        programme = join.programme_by_slug(slug, programme_slug)
        join.require_joiner(request.user)
        try:
            payload = join.presign_photo(programme, str(request.data.get("content_type", "")))
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(payload, status=status.HTTP_201_CREATED)


class InviteAcceptSerializer(serializers.Serializer):
    card = serializers.IntegerField(min_value=1)
    invite = serializers.CharField(max_length=64)


class InviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "id_join"

    @extend_schema(tags=["My cards"], summary="Accept an emailed programme invite (needs your verified email)",
                   request=InviteAcceptSerializer, responses={200: InviteAcceptResultSerializer, **errors(400, 401, 404, 429)})
    def post(self, request):
        data = InviteAcceptSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        card = invites.accept(request.user, data.validated_data["card"], data.validated_data["invite"])
        return Response({"card_id": card.pk, "status": card.status})
