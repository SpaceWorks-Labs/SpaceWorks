"""Desk instant print: one card face as a 300-dpi PNG on the chosen stock (O-B4, parity C19).

`GET admin/member-cards/<pk>/print-face?side=front|back&stock=<stock>`. The browser keeps both faces in
memory and prints them with `@page { size: <w>mm <h>mm }`, so printing works with the network down once
the faces are fetched. The card is drawn by the same renderer as downloads (`cards.render`); when the
chosen stock is bigger than the card it is centred on a white page of exactly that size at 300 dpi, and
scaled down when it is smaller. The card's `print_count` and the `member_card.printed` audit row move once
per card, on the FRONT face request. Needs `MANAGE_MEMBER_CARDS` and the `membership.card_desk_print` switch.
"""
import io

from django.http import HttpResponse
from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors

from .stocks import STOCKS
from .switches import DESK_PRINT

TAGS = ["Card designs"]
DPI = 300


def fit_to_stock(png, stock):
    """Centre the card PNG on a white page of the stock's size at 300 dpi (scaled down if it is bigger)."""
    from PIL import Image
    width_mm, height_mm = STOCKS[stock]
    size = (round(width_mm * DPI / 25.4), round(height_mm * DPI / 25.4))
    card = Image.open(io.BytesIO(png)).convert("RGB")
    if card.width > size[0] or card.height > size[1]:
        ratio = min(size[0] / card.width, size[1] / card.height)
        card = card.resize((max(1, int(card.width * ratio)), max(1, int(card.height * ratio))), Image.LANCZOS)
    page = Image.new("RGB", size, (255, 255, 255))
    page.paste(card, ((size[0] - card.width) // 2, (size[1] - card.height) // 2))
    out = io.BytesIO()
    page.save(out, format="PNG", dpi=(DPI, DPI))
    return out.getvalue(), size


class MemberCardPrintFaceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="One member card face for desk printing (PNG, 300 dpi)",
                   description="Audited once per card as `member_card.printed` (front face request). Off unless the "
                               "space turned on desk printing.",
                   parameters=[OpenApiParameter("side", str, enum=["front", "back"]),
                               OpenApiParameter("stock", str, enum=sorted(STOCKS), required=False,
                                                description="Centre the card on this stock; default: the card's own size.")],
                   request=None, responses={(200, "image/png"): OpenApiTypes.BINARY, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        from apps.makerspaces.member_card_admin_views_l3 import _card
        from apps.makerspaces.member_card_services import record_print
        from .cards import render
        card = _card(request.user, pk)
        if not feature_enabled(card.makerspace, DESK_PRINT):
            raise NotFound()  # decision 218
        if not card.is_active:
            raise PermissionDenied(gettext("A revoked card cannot be printed."))
        side, stock = request.query_params.get("side", "front"), request.query_params.get("stock")
        if side not in ("front", "back") or (stock and stock not in STOCKS):
            raise ValidationError({"detail": gettext("Choose the front or back, and a known stock.")})
        data, _type, filename = render("member_card", card, fmt="png", side=side)
        if stock:
            data, _size = fit_to_stock(data, stock)
        if side == "front":
            record_print(request.user, [card])
        response = HttpResponse(data, content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        return response
