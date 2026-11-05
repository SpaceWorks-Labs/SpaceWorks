"""Staff capture or upload a holder's card photo (X25, SPEC §5.2, §6).

Same storage rule as the holder's own upload: the browser only ever gets a presign for the
staging key; finalising reads, checks and promotes it server-side. The consent rule holds
for staff too: the staff member confirms the holder agreed to the photo being stored and
printed, and the attach is refused without that. Authority per kind, through each kind's
own staff resolver: member cards need MANAGE_MEMBER_CARDS in the card's space, programme
cards MANAGE_ID_PROGRAMMES on the host space, event cards an organiser of the event.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.openapi_errors import errors

TAGS = ["Card photos (staff)"]
TYPES = ("image/png", "image/jpeg", "image/webp")


class StaffPhotoPresignSerializer(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=TYPES)


class StaffPhotoFinalizeSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=300)
    content_type = serializers.ChoiceField(choices=TYPES, required=False, default="image/jpeg")
    holder_consented = serializers.BooleanField()


class StaffPhotoResultSerializer(serializers.Serializer):
    photo_set = serializers.BooleanField()


class _StaffCardPhotoView(APIView):
    permission_classes = [IsAuthenticated]
    kind = ""

    def card(self, request, pk):  # pragma: no cover - each subclass resolves its own kind
        raise NotImplementedError

    def _presign(self, card, content_type):
        if self.kind == "member_card":
            from apps.makerspaces.member_card_storage import presign_photo
            return presign_photo(card, content_type)
        from .photos import presign
        return presign(card, content_type)

    def _finalize(self, actor, card, values):
        consent = values["holder_consented"]
        if self.kind == "member_card":
            from apps.makerspaces.member_card_storage import finalize_photo
            return finalize_photo(actor, card, object_key=values["object_key"], content_type=values["content_type"],
                                  consent=consent)
        from .photos import finalize
        return finalize(actor, self.kind, card, object_key=values["object_key"], consent=consent)

    @extend_schema(tags=TAGS, summary="Start a holder photo upload for this card (staging presign only)",
                   request=StaffPhotoPresignSerializer, responses={201: OpenApiTypes.OBJECT, **errors(400, 401, 403, 404, 503)})
    def post(self, request, pk):
        card = self.card(request, pk)
        data = StaffPhotoPresignSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            return Response(self._presign(card, data.validated_data["content_type"]), status=status.HTTP_201_CREATED)
        except StorageUnavailable:
            return storage_unavailable_response()

    @extend_schema(tags=TAGS, summary="Attach the uploaded photo; the holder must have agreed",
                   request=StaffPhotoFinalizeSerializer,
                   responses={200: StaffPhotoResultSerializer, **errors(400, 401, 403, 404, 503)})
    def put(self, request, pk):
        card = self.card(request, pk)
        data = StaffPhotoFinalizeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            card = self._finalize(request.user, card, data.validated_data)
        except StorageUnavailable:
            return storage_unavailable_response()
        audit.record(request.user, "card.photo_set_by_staff", makerspace=card.makerspace, target=card,
                     meta={"holder_kind": self.kind, "card_id": card.pk, "holder_consented": True})
        return Response({"photo_set": True})


class MemberCardStaffPhotoView(_StaffCardPhotoView):
    kind = "member_card"

    def card(self, request, pk):
        from rest_framework.exceptions import ValidationError
        from apps.makerspaces.member_card_admin_views_l3 import _card
        card = _card(request.user, pk)
        if not card.is_active:
            raise ValidationError({"detail": "A revoked card cannot take a new photo."})
        return card


class ProgrammeCardStaffPhotoView(_StaffCardPhotoView):
    kind = "programme_card"

    def card(self, request, pk):
        from rest_framework.exceptions import ValidationError
        from apps.id_programmes.access import MANAGE, card_for
        card = card_for(request.user, pk, MANAGE)
        if card.status not in ("pending", "approved"):
            raise ValidationError({"detail": "Only a waiting or approved card can take a photo."})
        return card


class EventCardStaffPhotoView(_StaffCardPhotoView):
    kind = "event_card"

    def card(self, request, pk):
        from rest_framework.exceptions import ValidationError
        from apps.events.id_cards_views import organiser_card
        card = organiser_card(request.user, pk)
        if card.status != "active":
            raise ValidationError({"detail": "A revoked card cannot take a new photo."})
        return card
