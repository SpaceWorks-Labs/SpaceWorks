"""Parity O-B1: who sits in which unit, staff unit scope, plan-to-unit limits and the import review queue.

* `PUT admin/makerspaces/<id>/memberships/<mid>/unit` -- place a member (`manage_members`, narrowed by the
  caller's own unit scope: a member outside it is 404, a target unit outside it is `unit_scope_forbids`).
* `PUT admin/makerspaces/<id>/staff/<mid>/unit-scope` -- confine a staff membership to a unit's subtree
  (`manage_member_units`, needs `membership.unit_scoped_staff`; a scoped caller cannot change scopes).
* `GET/PUT admin/makerspaces/<id>/membership-plans/<pid>/units` -- limit a plan to units (the subtree inherits).
* `GET admin/makerspaces/<id>/member-import-reviews` and `POST .../<imported_id>/approve|reject` -- the unit
  lead's queue for imports run in verify mode.

All of them 404 when `membership.units` is off and across tenants.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.pii_presentation import MASK, pii_visible
from apps.admin_api import bulk_import_members_units as reviews
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_member_units import (
    MemberImportReviewSerializer, PlanUnitsSerializer, ReviewDecisionSerializer, UnitAssignmentResultSerializer,
    UnitAssignmentSerializer,
)
from apps.admin_api.views_membership_l4_common import staff_space
from apps.admin_api.views_roles import ERRORS
from apps.makerspaces import member_unit_assign as assign
from apps.makerspaces import member_unit_scope as scope
from apps.makerspaces import member_units
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan
from apps.makerspaces.models_member_units import ImportedMemberUnit, MembershipUnit, StaffUnitScope

TAG = "Admin member units"
MEMBERS, MANAGE = rbac.Action.MANAGE_MEMBERS, rbac.Action.MANAGE_MEMBER_UNITS


def _unit_dict(unit):
    if unit is None:
        return None
    return next(row for row in member_units.tree(unit.makerspace, include_archived=True) if row["id"] == unit.pk)


class MembershipUnitView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Put a member in a unit",
                   description="Requires manage_members and membership.units. `unit_id: null` removes the "
                               "member from their unit. An archived unit takes no new members.",
                   request=UnitAssignmentSerializer, responses={200: UnitAssignmentResultSerializer, **ERRORS})
    def put(self, request, makerspace_id, membership_id):
        space = staff_space(request.user, makerspace_id, "units", MEMBERS)
        membership = get_object_or_404(rbac.scope_by_action(
            request.user, MEMBERS, MakerspaceMembership.objects.filter(makerspace=space)), pk=membership_id)
        data = UnitAssignmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        assign.assign_member_unit(request.user, membership, data.validated_data["unit_id"], action=MEMBERS)
        row = MembershipUnit.objects.filter(membership=membership).select_related("unit").first()
        return Response({"membership_id": membership.pk, "unit": _unit_dict(row.unit) if row else None})


    @extend_schema(tags=[TAG], summary="Read the unit a member is in",
                   description="Same permission and scoping as the PUT: needs manage_members and membership.units, "
                               "cross-tenant is 404, and a unit-scoped caller only reads members in their own "
                               "subtree (others are 404). `unit` is null when the member has none. Not audited.",
                   responses={200: UnitAssignmentResultSerializer, **ERRORS})
    def get(self, request, makerspace_id, membership_id):
        space = staff_space(request.user, makerspace_id, "units", MEMBERS)
        membership = get_object_or_404(rbac.scope_by_action(
            request.user, MEMBERS, MakerspaceMembership.objects.filter(makerspace=space)), pk=membership_id)
        scope.require_member_in_scope(request.user, membership, MEMBERS)
        row = MembershipUnit.objects.filter(membership=membership).select_related("unit").first()
        return Response({"membership_id": membership.pk, "unit": _unit_dict(row.unit) if row else None})


class StaffUnitScopeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Confine a staff member to a unit",
                   description="Requires manage_member_units and membership.unit_scoped_staff. The member's "
                               "register, roster, requests, renewals and reports narrow to that unit and "
                               "everything under it. `unit_id: null` lifts the narrowing. Organization grants "
                               "and superadmin are never narrowed.",
                   request=UnitAssignmentSerializer, responses={200: UnitAssignmentResultSerializer, **ERRORS})
    def put(self, request, makerspace_id, membership_id):
        space = staff_space(request.user, makerspace_id, "unit_scoped_staff", MANAGE)
        staff = get_object_or_404(rbac.scope_by_action(
            request.user, MANAGE, MakerspaceMembership.staff_tracks.filter(makerspace=space)), pk=membership_id)
        data = UnitAssignmentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        assign.set_staff_unit_scope(request.user, staff, data.validated_data["unit_id"])
        row = StaffUnitScope.objects.filter(membership=staff).select_related("unit").first()
        return Response({"membership_id": staff.pk, "unit": _unit_dict(row.unit) if row else None})

    @extend_schema(tags=[TAG], summary="Read a staff member's unit scope",
                   responses={200: UnitAssignmentResultSerializer, **ERRORS})
    def get(self, request, makerspace_id, membership_id):
        space = staff_space(request.user, makerspace_id, "unit_scoped_staff", MANAGE)
        staff = get_object_or_404(rbac.scope_by_action(
            request.user, MANAGE, MakerspaceMembership.staff_tracks.filter(makerspace=space)), pk=membership_id)
        row = StaffUnitScope.objects.filter(membership=staff).select_related("unit").first()
        return Response({"membership_id": staff.pk, "unit": _unit_dict(row.unit) if row else None})


class PlanUnitsView(APIView):
    permission_classes = [IsActiveStaff]

    def _plan(self, request, makerspace_id, plan_id, action):
        space = staff_space(request.user, makerspace_id, "units", action)
        return get_object_or_404(rbac.scope_by_action(
            request.user, action, MembershipPlan.objects.filter(makerspace=space)), pk=plan_id)

    @extend_schema(tags=[TAG], summary="Which units a plan is limited to",
                   description="Empty means every unit.", responses={200: PlanUnitsSerializer, **ERRORS})
    def get(self, request, makerspace_id, plan_id):
        plan = self._plan(request, makerspace_id, plan_id, rbac.Action.VIEW_MEMBER_UNITS)
        return Response({"unit_ids": assign.plan_unit_ids(plan)})

    @extend_schema(tags=[TAG], summary="Limit a plan to units",
                   description="Requires manage_member_units. The plan is offered in each listed unit and "
                               "everything beneath it; an empty list offers it everywhere.",
                   request=PlanUnitsSerializer, responses={200: PlanUnitsSerializer, **ERRORS})
    def put(self, request, makerspace_id, plan_id):
        plan = self._plan(request, makerspace_id, plan_id, MANAGE)
        data = PlanUnitsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response({"unit_ids": assign.set_plan_units(request.user, plan, data.validated_data["unit_ids"])})


def _reviews_qs(request, space):
    rows = ImportedMemberUnit.objects.filter(makerspace=space, review_status=ImportedMemberUnit.Review.PENDING)
    return scope.narrow_by_unit_lookup(rows, request.user, space.pk, "unit__path", MEMBERS)


class MemberImportReviewListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Imported rows waiting for the unit lead",
                   description="Requires manage_members and membership.units. A unit-scoped lead sees only "
                               "their own unit's rows. Names and emails are masked without a PII window.",
                   responses={200: MemberImportReviewSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id, "units", MEMBERS)
        visible = pii_visible(request.user, space.pk)
        return Response([{
            "id": row.imported_id, "unit_id": row.unit_id, "review_status": row.review_status,
            "row_status": row.imported.status, "name": row.imported.name if visible else MASK,
            "email": row.imported.email if visible else MASK, "created_at": row.imported.created_at,
        } for row in _reviews_qs(request, space).select_related("imported", "unit")
            .order_by("imported__created_at")[:500]])


class _ReviewDecision(APIView):
    permission_classes = [IsActiveStaff]
    decide = None

    def post(self, request, makerspace_id, imported_id):
        space = staff_space(request.user, makerspace_id, "units", MEMBERS)
        get_object_or_404(_reviews_qs(request, space), imported_id=imported_id)
        row = type(self).decide(request.user, space, imported_id)
        return Response({"id": row.imported_id, "review_status": row.review_status})


class MemberImportReviewApproveView(_ReviewDecision):
    decide = staticmethod(reviews.approve_review)

    @extend_schema(tags=[TAG], summary="Approve an imported row",
                   description="Sends the normal invitation. Audited as member_unit.import_reviewed.",
                   request=None, responses={200: ReviewDecisionSerializer, **ERRORS})
    def post(self, request, makerspace_id, imported_id):
        return super().post(request, makerspace_id, imported_id)


class MemberImportReviewRejectView(_ReviewDecision):
    decide = staticmethod(reviews.reject_review)

    @extend_schema(tags=[TAG], summary="Reject an imported row",
                   description="The row is cancelled and nothing is sent.",
                   request=None, responses={200: ReviewDecisionSerializer, **ERRORS})
    def post(self, request, makerspace_id, imported_id):
        return super().post(request, makerspace_id, imported_id)
