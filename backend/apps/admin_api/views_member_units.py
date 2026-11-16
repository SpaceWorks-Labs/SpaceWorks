"""Parity O-B1: the member-unit tree (staff routes).

* `GET  admin/makerspaces/<id>/member-units` -- level names, templates, the tree and the allowance
  (`view_member_units`; a unit-scoped caller sees only their own subtree).
* `POST admin/makerspaces/<id>/member-units` -- create (`manage_member_units`, 201).
* `PATCH admin/makerspaces/<id>/member-units/<pk>`, `POST .../move`, `.../archive`, `.../restore`.
* `PUT  admin/makerspaces/<id>/member-unit-levels` -- name up to four levels.

Every route 404s when the space's `membership.units` switch is off, and 404s across tenants (the space is
resolved through `rbac`). Tree writes are space-wide: a unit-scoped actor gets the typed 403
`unit_scope_forbids`.
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_member_units import (
    MemberUnitCreateSerializer, MemberUnitDetailSerializer, MemberUnitLevelsSerializer, MemberUnitListSerializer,
    MemberUnitMoveSerializer, MemberUnitUpdateSerializer,
)
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import member_unit_scope as scope
from apps.makerspaces import member_units
from apps.makerspaces.models_member_units import MemberUnit

TAG = "Admin member units"
VIEW, MANAGE = rbac.Action.VIEW_MEMBER_UNITS, rbac.Action.MANAGE_MEMBER_UNITS


def _manage_space(request, makerspace_id):
    space = staff_space(request.user, makerspace_id, "units", MANAGE)
    scope.require_space_wide(request.user, space.pk, MANAGE)
    return space


def _unit(space, pk):
    return get_object_or_404(MemberUnit.objects.select_related("parent"), pk=pk, makerspace=space)


def detail(unit):
    row = next(item for item in member_units.tree(unit.makerspace, include_archived=True) if item["id"] == unit.pk)
    text, source = member_units.effective_payment_instructions(unit)
    return {**row, "payment_instructions": unit.payment_instructions, "effective_payment_instructions": text,
            "effective_instructions_unit_id": source.pk if source else None}


class MemberUnitListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="List the member units",
                   description="Requires view_member_units and membership.units. Archived units are listed only "
                               "with `archived=1`. A unit-scoped staff member sees their own subtree.",
                   parameters=[OpenApiParameter("archived", int, required=False)],
                   responses={200: MemberUnitListSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.managed_hosting.space_quotas import quota_limit
        from apps.managed_hosting.extra_quotas import extra_used
        space = staff_space(request.user, makerspace_id, "units", VIEW)
        rows = member_units.tree(space, include_archived=request.query_params.get("archived") == "1")
        prefixes = scope.unit_paths_for(request.user, space.pk, VIEW)
        if prefixes is not None:
            rows = [row for row in rows if any(row["path"].startswith(prefix) for prefix in prefixes)]
        return Response({"levels": member_units.level_names(space), "templates": [
            {**item, "levels": list(item["levels"])} for item in member_units.LEVEL_TEMPLATES],
            "units": rows, "limit": quota_limit(space, "member_units"),
            "used": extra_used(space, "member_units"), "scoped": prefixes is not None})

    @extend_schema(tags=[TAG], summary="Create a member unit",
                   description="Requires manage_member_units. The code is generated from the name when omitted. "
                               "Refused past the named levels (`member_unit_depth`) and past the `member_units` "
                               "allowance (409 `member_units_quota_reached`).",
                   request=MemberUnitCreateSerializer, responses={201: MemberUnitDetailSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _manage_space(request, makerspace_id)
        data = MemberUnitCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        unit = member_units.create_unit(request.user, space, **data.validated_data)
        return Response(detail(unit), status=status.HTTP_201_CREATED)


class MemberUnitDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Read one member unit", responses={200: MemberUnitDetailSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        space = staff_space(request.user, makerspace_id, "units", VIEW)
        unit = _unit(space, pk)
        prefixes = scope.unit_paths_for(request.user, space.pk, VIEW)
        if prefixes is not None and not any(unit.path.startswith(prefix) for prefix in prefixes):
            raise Http404()
        return Response(detail(unit))

    @extend_schema(tags=[TAG], summary="Edit a member unit",
                   description="Name, code (refused once the unit is in use: `member_unit_code_locked`), sort order "
                               "and offline payment instructions.",
                   request=MemberUnitUpdateSerializer, responses={200: MemberUnitDetailSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk):
        space = _manage_space(request, makerspace_id)
        data = MemberUnitUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        return Response(detail(member_units.update_unit(request.user, _unit(space, pk), dict(data.validated_data))))


class MemberUnitMoveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Move a unit (and its subtree)",
                   description="Refused when it would make a cycle (`member_unit_cycle`), go deeper than the named "
                               "levels (`member_unit_depth`) or land under an archived unit.",
                   request=MemberUnitMoveSerializer, responses={200: MemberUnitDetailSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = _manage_space(request, makerspace_id)
        data = MemberUnitMoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(detail(member_units.move_unit(request.user, _unit(space, pk), data.validated_data["parent_id"])))


class MemberUnitArchiveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Archive a member unit",
                   description="Archived, never deleted. Existing members keep their unit; nobody new can join it. "
                               "Refused while it has active child units (`member_unit_has_children`).",
                   request=None, responses={200: MemberUnitDetailSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = _manage_space(request, makerspace_id)
        return Response(detail(member_units.archive_unit(request.user, _unit(space, pk))))


class MemberUnitRestoreView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Restore an archived member unit", request=None,
                   responses={200: MemberUnitDetailSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = _manage_space(request, makerspace_id)
        return Response(detail(member_units.restore_unit(request.user, _unit(space, pk))))


class MemberUnitLevelsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Name the unit levels",
                   description="Up to four names, top level first. Refused while a unit uses a level being removed.",
                   request=MemberUnitLevelsSerializer, responses={200: MemberUnitLevelsSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        space = _manage_space(request, makerspace_id)
        data = MemberUnitLevelsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response({"levels": member_units.set_level_names(request.user, space, data.validated_data["levels"])})
