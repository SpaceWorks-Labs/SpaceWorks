"""The makerspace's financial-year start month (owner decision 71).

Reading it is open to anyone who works with the space's money or members (it labels
reports and documents). Changing it is a FINANCE setting: it goes through the
settings-authority layer (LANE-RULES §13), which keeps it the Space Manager's alone and
never delegable, and it is audited twice -- `settings.changed` (the cross-cutting
authority trail) and `makerspace.financial_year_updated`. Not module-gated: document
numbering (L5) reads it whether or not memberships are on.
"""
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.views_member_memberships import _makerspace
from apps.admin_api.views_roles import ERRORS
from apps.audit import services as audit
from apps.makerspaces.financial_year import SETTING_KEY, SETTING_MODULE, fy_bounds, fy_label
from apps.makerspaces.local_time import local_now
from apps.makerspaces.models import Makerspace
from apps.makerspaces.settings_authority import assert_setting_write, record_change

READERS = (rbac.Action.MANAGE_MAKERSPACE, rbac.Action.MANAGE_MEMBERS, rbac.Action.VIEW_FINANCE)


class FinancialYearSerializer(serializers.Serializer):
    financial_year_start_month = serializers.IntegerField(min_value=1, max_value=12)
    current_label = serializers.CharField(read_only=True)
    current_start = serializers.DateField(read_only=True)
    current_end = serializers.DateField(read_only=True)


def _payload(space):
    start, end = fy_bounds(space, local_now(space).date())
    return {"financial_year_start_month": space.financial_year_start_month,
            "current_label": fy_label(space, start), "current_start": start, "current_end": end}


def _readable_space(actor, makerspace_id):
    for action in READERS:
        if rbac.can(actor, action, makerspace_id):
            return _makerspace(actor, makerspace_id, action)
    raise PermissionDenied()


class FinancialYearView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin makerspaces"], summary="Read the financial-year start month",
        description="Requires manage_makerspace, manage_members or view_finance in this makerspace. "
                    "Also returns the current financial year's label and inclusive bounds.",
        responses={200: FinancialYearSerializer, **ERRORS},
    )
    def get(self, request, makerspace_id):
        return Response(FinancialYearSerializer(_payload(_readable_space(request.user, makerspace_id))).data)

    @extend_schema(
        tags=["Admin makerspaces"], summary="Change the financial-year start month",
        description="A finance setting: the Space Manager (or the superadmin) only, never delegable "
                    "(403 setting_not_delegated otherwise). Audited as settings.changed and "
                    "makerspace.financial_year_updated. Existing membership terms keep the end date "
                    "they were opened with.",
        request=FinancialYearSerializer,
        responses={200: FinancialYearSerializer, 400: OpenApiResponse(description="Invalid month."), **ERRORS},
    )
    def put(self, request, makerspace_id):
        space = _readable_space(request.user, makerspace_id)
        decision = assert_setting_write(request.user, space, SETTING_MODULE, SETTING_KEY)
        serializer = FinancialYearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        month = serializer.validated_data["financial_year_start_month"]
        with transaction.atomic():
            from apps.tenant_migration.gate_runtime import assert_write_allowed
            assert_write_allowed(space.pk)
            space = Makerspace.objects.select_for_update().get(pk=space.pk)
            previous = space.financial_year_start_month
            if previous != month:
                space.financial_year_start_month = month
                space.save(update_fields=["financial_year_start_month", "updated_at"])
                record_change(request.user, space, SETTING_MODULE, SETTING_KEY, previous, month, decision)
                audit.record(request.user, "makerspace.financial_year_updated", makerspace=space, target=space,
                             meta={"from_month": previous, "to_month": month})
        return Response(FinancialYearSerializer(_payload(space)).data)
