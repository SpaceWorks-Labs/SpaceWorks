"""Open item B13: staff routes for an organization's hours bank at one space.

`GET/PATCH .../makerspace/<id>/organizations/<org>/hours-bank/` reads and sets the allowance;
`GET/POST .../hours-bank/ledger/` lists the append-only ledger and appends a manual grant or adjustment.
Needs `manage_bookings` or `manage_members` in the space (scoped through `rbac`); a foreign space, an
organization that is not linked to the space, or an organization without bookings.organization_bookings all read
as not found / feature off. Organization admins read their own balance through `views_organization_hours_org`.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.guards import feature_off, require_module
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.organizations.models import Organization

from . import organization_hours_admin as service
from .organization_booking import FEATURE, organization_bookings_on
from .serializers_organization_hours import (
    OrganizationHoursAdjustSerializer, OrganizationHoursBankSerializer, OrganizationHoursBankWriteSerializer,
    OrganizationHoursLedgerPageSerializer, OrganizationHoursLedgerRowSerializer,
)
from .views_admin_booking_create import ERRORS
from .views_grant_pagination import PAGE_PARAMETERS

TAG = "Admin bookings"
CONTRACT = ("Requires manage_bookings or manage_members in the space and bookings.organization_bookings. A "
            "foreign space, or an organization not linked to the space, reads as not found.")


def linked_target(makerspace_id, organization_id):
    """`(makerspace, organization)` for a linked pair, else 404; the feature must be on."""
    space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
    require_module(space, "bookings")
    if not organization_bookings_on(space):
        raise feature_off(FEATURE)
    organization = Organization.objects.filter(
        pk=organization_id, makerspace_links__makerspace=space).first()
    if organization is None:
        raise NotFound()
    return space, organization


def staff_target(request, makerspace_id, organization_id):
    allowed = rbac.makerspaces_for_actions(request.user, rbac.Action.MANAGE_BOOKINGS, rbac.Action.MANAGE_MEMBERS)
    if allowed is not rbac.ALL and makerspace_id not in allowed:
        raise NotFound()
    return linked_target(makerspace_id, organization_id)


def ledger_page(request, rows, *, staff):
    paginator = PageNumberPagination()
    paginator.page_size = 24
    page = paginator.paginate_queryset(rows, request)
    response = paginator.get_paginated_response(
        OrganizationHoursLedgerRowSerializer(page, many=True, context={"staff": staff}).data)
    response["Cache-Control"] = "private, no-store"
    return response


class OrganizationHoursBankView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="An organization's hours bank at this space", description=CONTRACT,
                   responses={200: OrganizationHoursBankSerializer, **ERRORS})
    def get(self, request, makerspace_id, organization_id):
        space, organization = staff_target(request, makerspace_id, organization_id)
        return Response(OrganizationHoursBankSerializer(service.state(space, organization)).data,
                        headers={"Cache-Control": "private, no-store"})

    @extend_schema(tags=[TAG], summary="Set an organization's hours allowance", description=CONTRACT,
                   request=OrganizationHoursBankWriteSerializer,
                   responses={200: OrganizationHoursBankSerializer, **ERRORS})
    def patch(self, request, makerspace_id, organization_id):
        space, organization = staff_target(request, makerspace_id, organization_id)
        body = OrganizationHoursBankWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        service.update_allowance(space, organization, request.user, **body.validated_data)
        return Response(OrganizationHoursBankSerializer(service.state(space, organization)).data)


class OrganizationHoursLedgerView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="An organization's hours ledger (newest first)", description=CONTRACT,
                   parameters=PAGE_PARAMETERS, responses={200: OrganizationHoursLedgerPageSerializer, **ERRORS})
    def get(self, request, makerspace_id, organization_id):
        space, organization = staff_target(request, makerspace_id, organization_id)
        return ledger_page(request, service.ledger_rows(space, organization), staff=True)

    @extend_schema(tags=[TAG], summary="Grant or adjust an organization's hours",
                   description=CONTRACT + " A reason is required; the balance may not go below zero.",
                   request=OrganizationHoursAdjustSerializer,
                   responses={201: OrganizationHoursLedgerRowSerializer, **ERRORS})
    def post(self, request, makerspace_id, organization_id):
        space, organization = staff_target(request, makerspace_id, organization_id)
        body = OrganizationHoursAdjustSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = service.adjust(space, organization, request.user, **body.validated_data)
        return Response(OrganizationHoursLedgerRowSerializer(row, context={"staff": True}).data, status=201)
