"""Archive and restore a membership plan (X5).

An archived plan stays on every term sold under it (terms PROTECT their plan) but is
hidden from the public listing, the join form and new terms. Plan definitions are the
Space Manager's (`manage_makerspace`), like every other plan edit. Audited as
`membership.plan_archived` / `membership.plan_restored`.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_membership_plans import MembershipPlanSerializer
from apps.admin_api.views_membership_plans import _gated_makerspace
from apps.admin_api.views_roles import ERRORS
from apps.audit import services as audit
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import MembershipPlan


def _plan(actor, pk):
    return get_object_or_404(
        rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE, MembershipPlan.objects.all()), pk=pk)


def _set_archived(actor, plan, archived):
    _gated_makerspace(actor, plan.makerspace_id, rbac.Action.MANAGE_MAKERSPACE)
    with transaction.atomic():
        makerspace = require_module_locked(plan.makerspace_id, "membership")
        plan = MembershipPlan.objects.select_for_update().get(pk=plan.pk)
        if (plan.archived_at is not None) != archived:
            plan.archived_at = timezone.now() if archived else None
            plan.save(update_fields=["archived_at", "updated_at"])
            if archived:
                audit.record(actor, "membership.plan_archived", makerspace=makerspace, target=plan,
                             meta={"plan_id": plan.pk})
            else:
                audit.record(actor, "membership.plan_restored", makerspace=makerspace, target=plan,
                             meta={"plan_id": plan.pk})
    return plan


class MembershipPlanArchiveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin memberships"], summary="Archive a membership plan",
                   description="Requires manage_makerspace. Terms keep the plan; it leaves the public "
                               "listing, the join form and new terms. Idempotent; audited.",
                   request=None, responses={200: MembershipPlanSerializer, **ERRORS})
    def post(self, request, pk):
        return Response(MembershipPlanSerializer(_set_archived(request.user, _plan(request.user, pk), True)).data)

    @extend_schema(tags=["Admin memberships"], summary="Restore an archived membership plan",
                   description="Requires manage_makerspace. Idempotent; audited.",
                   request=None, responses={200: MembershipPlanSerializer, **ERRORS})
    def delete(self, request, pk):
        return Response(MembershipPlanSerializer(_set_archived(request.user, _plan(request.user, pk), False)).data)
