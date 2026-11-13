"""Member-facing card endpoints: the caller's OWN card only."""
from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.accounts import rbac
from apps.audit import services as audit
from apps.card_designs.serializers_openapi import PhotoUploadSerializer
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import member_card_storage
from apps.makerspaces.member_card_serializers import (
    MemberCardOwnUpdateSerializer,
    MemberCardPhotoFinalizeSerializer,
    MemberCardPhotoPresignSerializer,
    MemberCardSerializer,
)
from apps.makerspaces.models import MemberCard
from apps.makerspaces.profile_views import MemberProfileBaseView
from apps.makerspaces.throttles import MemberImagePresignThrottle
from apps.makerspaces.member_card_own_serializer import OwnMemberCardSerializer

ERRORS = {
    400: OpenApiResponse(description="Invalid input."),
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(description="An active membership is required."),
    404: OpenApiResponse(description="No card has been issued to this membership, or the membership module is turned off."),
}


class OwnMemberCardMixin(MemberProfileBaseView):
    def card(self, request, makerspace_id):
        membership = self.membership(request, makerspace_id)
        card = rbac.scope_by_makerspace(
            request.user, MemberCard.objects.select_related("makerspace", "membership__assigned_role"),
        ).filter(
            membership=membership, revoked_at__isnull=True
        ).first()
        if card is None:
            raise Http404
        return card


class MemberCardOwnView(OwnMemberCardMixin):
    @extend_schema(tags=["Member profile"], summary="Read my member card", request=None,
                   responses={200: OwnMemberCardSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        response = Response(OwnMemberCardSerializer(self.card(request, makerspace_id)).data)
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(tags=["Member profile"], summary="Set the name printed on my card",
                   request=MemberCardOwnUpdateSerializer, responses={200: MemberCardSerializer, **ERRORS})
    def patch(self, request, makerspace_id):
        card = self.card(request, makerspace_id)
        serializer = MemberCardOwnUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        card.printed_name = serializer.validated_data["printed_name"]
        card.save(update_fields=["printed_name", "updated_at"])
        audit.record(request.user, "member_card.name_updated", makerspace=card.makerspace, target=card, meta={"card_id": card.pk})
        return Response(MemberCardSerializer(card).data)


class MemberCardPhotoView(OwnMemberCardMixin):
    throttle_classes = [MemberImagePresignThrottle]

    @extend_schema(tags=["Member profile"], summary="Create a card photo upload URL (staging only)",
                   request=MemberCardPhotoPresignSerializer, responses={201: PhotoUploadSerializer, **ERRORS,
                   503: OpenApiResponse(description="Storage unavailable.")})
    def post(self, request, makerspace_id):
        card = self.card(request, makerspace_id)
        serializer = MemberCardPhotoPresignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = member_card_storage.presign_photo(card, serializer.validated_data["content_type"])
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["Member profile"], summary="Attach an uploaded card photo (requires consent)",
                   request=MemberCardPhotoFinalizeSerializer, responses={200: MemberCardSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        card = self.card(request, makerspace_id)
        serializer = MemberCardPhotoFinalizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            card = member_card_storage.finalize_photo(
                request.user, card, object_key=data["object_key"],
                content_type=data["content_type"], consent=data["consent"],
            )
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(MemberCardSerializer(card).data)

    @extend_schema(tags=["Member profile"], summary="Remove my card photo", request=None,
                   responses={200: MemberCardSerializer, **ERRORS})
    def delete(self, request, makerspace_id):
        card = self.card(request, makerspace_id)
        if card.photo_object_key:
            member_card_storage.delete_photo(card)
            card.photo_object_key = ""
            card.photo_content_type = ""
            card.photo_size_bytes = None
            card.photo_consent_at = None
            card.photo_consent_version = ""
            card.save(update_fields=["photo_object_key", "photo_content_type", "photo_size_bytes",
                                     "photo_consent_at", "photo_consent_version", "updated_at"])
            audit.record(request.user, "member_card.photo_removed", makerspace=card.makerspace, target=card, meta={"card_id": card.pk})
        return Response(MemberCardSerializer(card).data)


class MemberCardPreviewView(OwnMemberCardMixin):
    @extend_schema(tags=["Member profile"], summary="Preview my card as a watermarked PDF", request=None,
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.card_designs.cards import render
        card = self.card(request, makerspace_id)
        # Release 2 L3: the real design, watermarked, with placeholder codes.
        pdf, _content_type, _filename = render("member_card", card, fmt="pdf", preview_label="PREVIEW - not valid")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="member-card-preview.pdf"'
        return response
