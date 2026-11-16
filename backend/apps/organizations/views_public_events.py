"""Optional P5 upcoming/archive event collection, retaining the global target."""
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from apps.apiclients.throttling import ClientTierRateThrottle
from .public_catalog import public_events_for
from .serializers_public_events import PublicOrganizationEventSerializer, PublicOrganizationEventListSerializer, OrganizationArchiveListSerializer
from .serializers_public import OrganizationArchiveEventSerializer
from .views_public import _public_organization, COLLECTION_ERRORS


class PublicOrganizationEventListView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(
        tags=["Public organizations"],
        summary="List public events organized across makerspaces",
        auth=[],
        request=None,
        parameters=[OpenApiParameter("period", str, enum=["upcoming", "past"]), OpenApiParameter("page", int)],
        responses={200: PolymorphicProxySerializer(component_name="OrganizationEventCollection",
            serializers={"upcoming": PublicOrganizationEventListSerializer, "past": OrganizationArchiveListSerializer},
            resource_type_field_name="period"), **COLLECTION_ERRORS},
    )
    def get(self, request, slug):
        from apps.makerspaces.public_page_pagination import PagePagination
        from .public_catalog import archive_card
        from rest_framework.exceptions import ValidationError
        # This legacy catalogue shares the global profile's compatibility admission.
        # Its queryset independently enforces organizer, host and event visibility.
        organization = _public_organization(slug)
        period = request.query_params.get("period", "upcoming")
        if period not in {"upcoming", "past"}:
            raise ValidationError({"period": gettext("Choose upcoming or past.")})
        paginator = PagePagination()
        rows = public_events_for(organization, period=period)
        page = paginator.paginate_queryset(rows if rows is not None else [], request, view=self)
        result = (OrganizationArchiveEventSerializer([archive_card(row) for row in page], many=True).data
                  if period == "past" else PublicOrganizationEventSerializer(page, many=True, context={"omit_website": True}).data)
        response = paginator.get_paginated_response(result)
        response.data["period"] = period
        response["Cache-Control"] = "no-store"
        return response

