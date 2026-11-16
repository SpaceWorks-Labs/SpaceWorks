import json

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.utils.encoders import JSONEncoder
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.inventory.public_stats import build_public_stats
from apps.inventory.public_stats_cache import cached
from apps.inventory.public_stats_serializers import PublicStatsPageSerializer
from apps.makerspaces.lookup import get_public_makerspace
from apps.openapi import PUBLIC_API_AUTH_PARAMETERS


@extend_schema(
    tags=["Public inventory"],
    summary="Get public makerspace stats",
    description=(
        "Get public activity stats for a public makerspace: the sections, order, fixed period, headline "
        "numbers and TV refresh its Space Manager chose in Settings › Public stats. A section whose module "
        "is off is left out; 404 while the page is off or no section is left to show. Counts below 3 are "
        "published as suppressed. Served from a short per-space cache."
    ),
    parameters=[
        *PUBLIC_API_AUTH_PARAMETERS,
        OpenApiParameter(
            name="makerspace_slug",
            type=str,
            location=OpenApiParameter.PATH,
            description="Public makerspace code (for example TSEL) or slug.",
        ),
    ],
    responses=PublicStatsPageSerializer,
)
class PublicMakerspaceStatsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_stats"

    def get(self, request, makerspace_slug):
        makerspace = get_public_makerspace(makerspace_slug)
        if not (makerspace.public_stats_enabled and makerspace.public_site_enabled):
            raise Http404
        data = cached(makerspace, lambda: _plain(PublicStatsPageSerializer(build_public_stats(makerspace)).data))
        # Every section gated off (modules, editions, the catalogue switch) is no page at all.
        if not data["sections"]:
            raise Http404
        return Response(data)


def _plain(data):
    """Serializer output as plain JSON values: what the cache stores and every hit returns."""
    return json.loads(json.dumps(data, cls=JSONEncoder))
