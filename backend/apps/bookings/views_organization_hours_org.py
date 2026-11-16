"""Open item B13: organization admins READ their own organization's hours bank (balance and ledger).

Global organization routes: the caller must be an active member of the organization holding an organization
governance action (profile or members), or a superadmin; anyone else reads as not found. Nothing is written.
The staff routes that set the allowance live in `views_organization_hours`.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.organizations import governance
from apps.organizations.access import visible_organizations
from apps.organizations.models import OrganizationMakerspace
from apps.organizations.views_console import console_errors

from . import organization_hours_admin as service
from .models_organization_hours import OrganizationHoursAllowance
from .organization_hours import applies
from .serializers_organization_hours import (
    OrganizationHoursBanksSerializer, OrganizationHoursLedgerPageSerializer,
)
from .views_grant_pagination import PAGE_PARAMETERS
from .views_organization_hours import ledger_page

TAG = "Admin organizations"
CONTRACT = ("Requires an active organization admin role (profile or members governance) in this organization, "
            "or a superadmin. Anyone else, and an organization with no bank at the space, reads as not found.")


def admin_organization(actor, pk):
    organization = get_object_or_404(visible_organizations(actor), pk=pk)
    if not governance.actions_for(actor, organization):
        raise NotFound()
    return organization


class OrganizationOwnHoursBankView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="This organization's hours balance at each space", description=CONTRACT,
                   responses={200: OrganizationHoursBanksSerializer, **console_errors(401, 403, 404)})
    def get(self, request, pk):
        organization = admin_organization(request.user, pk)
        banked = set(OrganizationHoursAllowance.objects.filter(organization=organization)
                     .values_list("makerspace_id", flat=True))
        links = OrganizationMakerspace.objects.filter(
            organization=organization, makerspace_id__in=banked).select_related("makerspace")
        banks = []
        for link in links.order_by("makerspace__name")[:100]:
            if servable_queryset(Makerspace.objects.filter(pk=link.makerspace_id)).exists() \
                    and applies(link.makerspace):
                banks.append({**service.state(link.makerspace, organization), "makerspace_name": link.makerspace.name})
        return Response(OrganizationHoursBanksSerializer({"banks": banks}).data,
                        headers={"Cache-Control": "private, no-store"})


class OrganizationOwnHoursLedgerView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="This organization's hours ledger at one space", description=CONTRACT,
                   parameters=PAGE_PARAMETERS,
                   responses={200: OrganizationHoursLedgerPageSerializer, **console_errors(401, 403, 404)})
    def get(self, request, pk, makerspace_id):
        organization = admin_organization(request.user, pk)
        link = get_object_or_404(OrganizationMakerspace.objects.select_related("makerspace"),
                                 organization=organization, makerspace_id=makerspace_id)
        if not servable_queryset(Makerspace.objects.filter(pk=makerspace_id)).exists() or not applies(link.makerspace):
            raise NotFound()
        return ledger_page(request, service.ledger_rows(link.makerspace, organization), staff=False)
