"""Organisation default member-card design (O-B4): one design, every space the organisation owns."""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import org_default
from .serializers import CardDesignCreateSerializer, CardDesignSerializer

TAGS = ["Card designs"]


class OrganizationMemberCardDesignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read the organisation's default member-card design",
                   description="`null` until one is created. Needs member-card management in every space the "
                               "organisation owns; anyone else gets a 404.",
                   request=None, responses={200: CardDesignSerializer(allow_null=True), **errors(401, 404)})
    def get(self, request, organization_id):
        org_default.organization_for(request.user, organization_id)
        row = org_default.existing(organization_id)
        return Response(CardDesignSerializer(row, context={"request": request}).data if row else None)

    @extend_schema(tags=TAGS, summary="Create the organisation's default member-card design",
                   description="The default for the one member card in every space the organisation owns, "
                               "ahead of each space's own default. Edit, submit and publish it like any design.",
                   request=CardDesignCreateSerializer,
                   responses={201: CardDesignSerializer, 200: CardDesignSerializer, **errors(400, 401, 404)})
    def post(self, request, organization_id):
        organization = org_default.organization_for(request.user, organization_id)
        data = CardDesignCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row, created = org_default.create(request.user, organization, template=data.validated_data.get("template"),
                                          theme=data.validated_data["theme"])
        return Response(CardDesignSerializer(row, context={"request": request}).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
