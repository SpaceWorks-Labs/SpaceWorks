"""The holder's "My cards" (SPEC §8): list, download, email me, check-link and extras opt-ins."""
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.openapi_errors import errors

from . import extras, tokens
from .holder_access import my_cards, own_card
from .lifecycle import public_verify_on
from .models import CardPhotoRequest

TAGS = ["My cards"]
KIND_CHOICES = ("member_card", "programme_card", "event_card")


class MyCardSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    id = serializers.IntegerField()
    makerspace_id = serializers.IntegerField()
    issuer = serializers.CharField()
    title = serializers.CharField()
    name = serializers.CharField()
    number = serializers.CharField()
    label = serializers.CharField()
    valid_until = serializers.CharField()
    status = serializers.ChoiceField(choices=("valid", "expired", "revoked"))
    has_back = serializers.BooleanField()
    check_url = serializers.CharField(allow_blank=True)
    photo_request_open = serializers.BooleanField()
    wallet_platforms = serializers.ListField(child=serializers.CharField())
    email_available = serializers.BooleanField()
    qr_image = serializers.CharField(allow_null=True)


class CardSettingsSerializer(serializers.Serializer):
    verify_show_name = serializers.BooleanField(required=False)
    verify_show_photo = serializers.BooleanField(required=False)
    extras_opted_in = serializers.BooleanField(required=False)
    blood_group = serializers.CharField(required=False, allow_blank=True, max_length=3)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    public_check_on = serializers.BooleanField(read_only=True)


def _row(kind, spec, card, standing):
    from .email import blocked
    from .switches import wallet_on
    from .wallet.credentials import configured_platforms
    values = spec.snapshot(card)
    token = tokens.live(kind, card) if standing != "revoked" else None
    document, _design = spec.design(card)
    return {"kind": kind, "id": card.pk, "makerspace_id": card.makerspace_id, "issuer": spec.issuer(card)["name"],
            "title": {"member_card": "Member card", "programme_card": values.get("programme", "ID card"),
                      "event_card": values.get("event", "Event card")}[kind],
            "name": values.get("name", ""), "number": values.get("number", ""), "label": spec.label(card) or "",
            "valid_until": values.get("valid_until", ""), "status": standing,
            "has_back": bool(document.get("back_enabled")),
            "check_url": tokens.url(token.token) if token and public_verify_on(kind, card) else "",
            "photo_request_open": CardPhotoRequest.objects.filter(**{kind: card}, resolved_at__isnull=True).exists(),
            "wallet_platforms": list(configured_platforms()) if standing == "valid" and wallet_on(kind, card.makerspace)
            else [], "email_available": not blocked(card.makerspace), "qr_image": _qr_image(kind, spec, card, token,
                                                                                          standing)}


def _qr_image(kind, spec, card, token, standing):
    """The QR shown on the ticket view: the desk QR for member cards, the check QR otherwise."""
    import segno
    if standing == "revoked":
        return None
    payload = spec.desk_payload(card) if kind == "member_card" else (tokens.url(token.token) if token else None)
    return segno.make(payload).png_data_uri(scale=6) if payload else None


class MyCardsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="My cards across every space, programme and event", request=None,
                   responses={200: MyCardSerializer(many=True), **errors(401)})
    def get(self, request):
        response = Response([_row(*row) for row in my_cards(request.user)])
        response["Cache-Control"] = "no-store"
        return response


class MyCardDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download my card (PDF, or one side as PNG)", request=None,
                   parameters=[OpenApiParameter("format", str, enum=["pdf", "png"]),
                               OpenApiParameter("side", str, enum=["front", "back"])],
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, (200, "image/png"): OpenApiTypes.BINARY,
                              **errors(400, 401, 403, 404)})
    def get(self, request, kind, card_id):
        from .cards import render
        from .downloads import record_download
        spec, card = own_card(request.user, kind, card_id)
        if spec.standing(card) == "revoked":
            raise PermissionDenied("This card was revoked.")
        fmt, side = request.query_params.get("format", "pdf"), request.query_params.get("side", "front")
        data, content_type, filename = render(kind, card, fmt=fmt, side=side)
        record_download(request.user, kind, card, fmt, side)
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        return response


class MyCardEmailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Email me my card (PDF attached)", request=None,
                   responses={202: OpenApiTypes.OBJECT, **errors(400, 401, 404)})
    def post(self, request, kind, card_id):
        from .email import blocked, send_card_email
        _spec, card = own_card(request.user, kind, card_id)
        if blocked(card.makerspace):
            raise ValidationError({"detail": "Email is turned off for this space."})
        if not send_card_email(kind, card, actor=request.user, explicit=True):
            raise ValidationError({"detail": "Your card was emailed a few minutes ago. Try again later."})
        return Response({"queued": True}, status=202)


class MyCardSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, kind, card):
        values = extras.read(kind, card)
        return {"verify_show_name": card.verify_show_name, "verify_show_photo": card.verify_show_photo,
                "extras_opted_in": values["opted_in"], "blood_group": values["blood_group"],
                "emergency_contact_name": values["emergency_contact_name"],
                "emergency_contact_phone": values["emergency_contact_phone"],
                "public_check_on": public_verify_on(kind, card)}

    @extend_schema(tags=TAGS, summary="My card's check-page and extras choices", request=None,
                   responses={200: CardSettingsSerializer, **errors(401, 404)})
    def get(self, request, kind, card_id):
        _spec, card = own_card(request.user, kind, card_id)
        return Response(self._payload(kind, card))

    @extend_schema(tags=TAGS, summary="Choose what the check page shows, and the opt-in extras",
                   description="Blood group and emergency contact are opt-in, encrypted, printed only where the "
                               "design places them, and never shown to staff, on the check page or in a wallet pass.",
                   request=CardSettingsSerializer, responses={200: CardSettingsSerializer, **errors(400, 401, 404)})
    def patch(self, request, kind, card_id):
        from django.utils import timezone
        _spec, card = own_card(request.user, kind, card_id)
        data = CardSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        changed = [name for name in ("verify_show_name", "verify_show_photo")
                   if name in values and values[name] != getattr(card, name)]
        if changed:
            for name in changed:
                setattr(card, name, values[name])
            card.verify_consent_at = timezone.now()
            card.save(update_fields=[*changed, "verify_consent_at", "updated_at"])
            audit.record(request.user, "card.verify_optin_changed", makerspace=card.makerspace, target=card,
                         meta={"card_id": card.pk, "holder_kind": kind, "fields": changed})
        if "extras_opted_in" in values:
            extras.write(request.user, kind, card, opted_in=values["extras_opted_in"],
                         blood_group=values.get("blood_group", ""),
                         emergency_contact_name=values.get("emergency_contact_name", ""),
                         emergency_contact_phone=values.get("emergency_contact_phone", ""))
        return Response(self._payload(kind, card))


class MyCardRotateLinkView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Rotate my check link (the old printed QR stops working)", request=None,
                   responses={200: OpenApiTypes.OBJECT, **errors(400, 401, 404)})
    def post(self, request, kind, card_id):
        _spec, card = own_card(request.user, kind, card_id)
        if not public_verify_on(kind, card):
            raise ValidationError({"detail": "The public check page is off for this card."})
        token = tokens.rotate(kind, card)
        audit.record(request.user, "card.verify_link_rotated", makerspace=card.makerspace, target=card,
                     meta={"card_id": card.pk, "holder_kind": kind})
        return Response({"check_url": tokens.url(token.token),
                         "reprint_needed": "Ask staff to reprint your card: the printed QR now reads as revoked."})
