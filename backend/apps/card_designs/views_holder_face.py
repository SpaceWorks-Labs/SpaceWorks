"""The holder's printed-card view (SPEC §8 "Printed card view"): the design drawn in the browser.

`face` returns what the browser needs to draw the published design itself -- the normalised
document, the card's own field values, its photo, logos, design artwork and both QR codes
as inline data -- so the wallet shows the real design front and back as vector layers.
The server PDF/PNG stays the source of truth for printing. Only the holder reads this,
for a live (not revoked) card; the opt-in extras appear only when the holder opted in,
exactly as on the printed card. `fonts` serves the card fonts the design uses, from this
app (never a font CDN).
"""
import base64

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from .holder_access import own_card

TAGS = ["My cards"]
SENSITIVE = ("blood_group", "emergency_contact")
MAGIC = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"RIFF", "image/webp"))


def data_uri(data):
    if not data:
        return None
    mime = next((kind for magic, kind in MAGIC if data.startswith(magic)), None)
    if mime is None and data.lstrip()[:5] in (b"<?xml", b"<svg "):
        mime = "image/svg+xml"
    if mime is None:
        return None
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def qr_uri(payload):
    import segno
    return segno.make(payload, error="m").svg_data_uri(border=4, dark="#000000", light="#FFFFFF") if payload else None


def live_card(user, kind, card_id):
    spec, card = own_card(user, kind, card_id)
    if spec.standing(card) == "revoked":
        raise PermissionDenied("This card was revoked.")
    return spec, card


def face(kind, card):
    from .cards import context_for, document_for
    document = document_for(kind, card)
    context = context_for(kind, card, document)
    values = {key: value for key, value in context.values.items()
              if context.allow_sensitive or key not in SENSITIVE}
    return {"document": document, "values": {key: "" if value is None else str(value) for key, value in values.items()},
            "photo": data_uri(context.photo),
            "logos": {name: data_uri(data) for name, data in (context.logos or {}).items()},
            "assets": {key: data_uri(data) for key, data in (context.assets or {}).items()},
            "desk_qr": qr_uri(context.desk_qr), "verify_qr": qr_uri(context.verify_qr)}


class MyCardFaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="My card's published design and values, for the printed-card view",
                   request=None, responses={200: OpenApiTypes.OBJECT, **errors(401, 403, 404)})
    def get(self, request, kind, card_id):
        _spec, card = live_card(request.user, kind, card_id)
        response = Response(face(kind, card))
        response["Cache-Control"] = "private, no-store"
        return response


class MyCardFontView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, operation_id="member_card_font_file",
                   summary="A card font my card's design uses (served by this app, never Google)", request=None,
                   responses={(200, "font/ttf"): OpenApiTypes.BINARY, **errors(401, 403, 404)})
    def get(self, request, kind, card_id, family_slug, weight):
        from . import font_store, fonts
        from .cards import document_for
        _spec, card = live_card(request.user, kind, card_id)
        document = document_for(kind, card)
        used = {layer.get("font_family") for side in ("front", "back")
                for layer in (document.get(side) or {}).get("layers", ()) if layer.get("font_family")}
        family = next((name for name in used if fonts.slug(name) == family_slug), None)
        data = font_store.font_bytes(family, weight) if family else None
        if data is None:
            raise NotFound()
        response = HttpResponse(data, content_type="font/ttf")
        response["Cache-Control"] = "private, max-age=86400"
        return response
