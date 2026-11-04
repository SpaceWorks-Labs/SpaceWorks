"""Staff routes for programmes: list/create per organisation, read/change/delete one,
its design, its approval switch. Authority by action on the host space (`access`)."""
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import services
from .access import MANAGE, programme_for, programmes_for
from .serializers import IdProgrammeCreateSerializer, IdProgrammeSerializer

TAGS = ["ID programmes"]


class OrganizationProgrammeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Programmes this organisation runs (that you can see)", request=None,
                   responses={200: IdProgrammeSerializer(many=True), **errors(401)})
    def get(self, request, organization_id):
        from apps.card_designs.switches import programmes_on
        rows = [row for row in programmes_for(request.user).filter(organization_id=organization_id)
                if programmes_on(row.makerspace)]
        return Response(IdProgrammeSerializer(rows, many=True, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Create a programme hosted by a space this organisation owns",
                   request=IdProgrammeCreateSerializer,
                   responses={201: IdProgrammeSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, organization_id):
        from django.http import Http404
        from apps.card_designs.switches import programmes_on
        from apps.makerspaces.models import Makerspace
        from apps.organizations.models import Organization
        data = IdProgrammeCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        organization = get_object_or_404(Organization, pk=organization_id, is_active=True)
        space = get_object_or_404(Makerspace, pk=data.validated_data["makerspace_id"])
        if not programmes_on(space):
            raise Http404
        values = {"name": data.validated_data["name"], "preset": data.validated_data.get("preset", "")}
        programme = services.create(request.user, organization, space, values)
        return Response(IdProgrammeSerializer(programme, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


class ProgrammeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a programme", request=None,
                   responses={200: IdProgrammeSerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(IdProgrammeSerializer(programme_for(request.user, pk), context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Change a programme's settings or questions", request=IdProgrammeSerializer,
                   responses={200: IdProgrammeSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        programme = programme_for(request.user, pk, MANAGE)
        data = IdProgrammeSerializer(programme, data=request.data, partial=True, context={"request": request})
        data.is_valid(raise_exception=True)
        programme = services.update(request.user, programme, data.validated_data)
        return Response(IdProgrammeSerializer(programme, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Delete a programme that never approved a card (else close it)", request=None,
                   responses={204: None, **errors(400, 401, 403, 404)})
    def delete(self, request, pk):
        services.delete(request.user, programme_for(request.user, pk, MANAGE))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProgrammeDesignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="The programme's card design (edit it through the card-design routes)",
                   request=None, responses={200: OpenApiTypes.OBJECT, **errors(401, 403, 404)})
    def get(self, request, pk):
        from apps.card_designs.resolution import get_or_create
        from apps.card_designs.serializers import CardDesignSerializer
        programme = programme_for(request.user, pk, MANAGE)
        design, _created = get_or_create(programme.makerspace, "id_programme", actor=request.user, programme=programme)
        return Response(CardDesignSerializer(design, context={"request": request}).data)


class ProgrammeApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Whether this programme's design edits need approval (#136)",
                   request={"application/json": {"type": "object", "properties": {"required": {"type": "boolean"}}}},
                   responses={200: OpenApiTypes.OBJECT, **errors(400, 401, 403, 404)})
    def put(self, request, pk):
        from rest_framework.exceptions import ValidationError
        from apps.card_designs.approval import set_level
        from apps.makerspaces.settings_authority import assert_setting_write
        programme = programme_for(request.user, pk, MANAGE)
        required = request.data.get("required")
        if type(required) is not bool:
            raise ValidationError({"required": "Use true or false."})
        assert_setting_write(request.user, programme.makerspace, "membership", "card_designs.approval")
        set_level(request.user, programme.makerspace, "membership", required, programme=programme)
        return Response({"required": required})
