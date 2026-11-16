"""`GET /api/v1/public/<slug>/events/<token>/share.png`: the event's share image (L1, G5)."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.public_page_access import require_scope

from .share_cards import share_png
from .website_visibility import resolve


class PublicEventShareImageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(
        tags=["Public events"], auth=[], summary="Event share image (PNG, 1200x630)",
        description="Live-gated like the event page: private, draft, ended and offline events are 404; "
                    "unlisted events are served with `X-Robots-Tag: noindex, nofollow`. Never carries the "
                    "join link.",
        responses={(200, "image/png"): OpenApiResponse(OpenApiTypes.BINARY, description="PNG image."),
                   404: OpenApiResponse(ErrorSerializer, description="Unknown or unavailable event."),
                   429: OpenApiResponse(ErrorSerializer, description="Rate limit exceeded.")},
    )
    def get(self, request, makerspace_slug, public_token):
        event = resolve(makerspace_slug, public_token)
        require_scope("makerspace", event.makerspace, request)
        response = HttpResponse(share_png(event), content_type="image/png")
        # Live gates run on every request; only the rendered bytes are cached server-side.
        response["Cache-Control"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        from .views_public_codes import robots
        return robots(response, event)
