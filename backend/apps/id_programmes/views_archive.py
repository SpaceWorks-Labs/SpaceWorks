"""Archive and restore an ID programme (owner decision 219(h)); see `services.archive`."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import services
from .access import MANAGE, programme_for
from .serializers import IdProgrammeSerializer

TAGS = ["ID programmes"]


class ProgrammeArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Archive a programme: it closes and leaves active lists; cards are kept",
                   request=None, responses={200: IdProgrammeSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        programme = services.archive(request.user, programme_for(request.user, pk, MANAGE))
        return Response(IdProgrammeSerializer(programme, context={"request": request}).data)


class ProgrammeUnarchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Restore an archived programme to the active list (it stays closed)",
                   request=None, responses={200: IdProgrammeSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        programme = services.unarchive(request.user, programme_for(request.user, pk, MANAGE))
        return Response(IdProgrammeSerializer(programme, context={"request": request}).data)
