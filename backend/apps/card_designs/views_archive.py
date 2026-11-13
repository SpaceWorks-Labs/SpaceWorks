"""Archive and restore a card-design override (owner decision 219(h)); see `archive`."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import archive
from .authority import design_for, require_edit
from .serializers import CardDesignSerializer

TAGS = ["Card designs"]


class CardDesignArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Archive an override: holders fall back to the next design; history stays",
                   request=None, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        design = archive.archive(request.user, require_edit(request.user, design_for(request.user, pk)))
        return Response(CardDesignSerializer(design, context={"request": request}).data)


class CardDesignUnarchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Restore an archived override so holders use it again",
                   request=None, responses={200: CardDesignSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        design = archive.unarchive(request.user, require_edit(request.user, design_for(request.user, pk)))
        return Response(CardDesignSerializer(design, context={"request": request}).data)
