"""Cancellation refund policy per area, and per membership plan. Editing needs manage_makerspace."""

from django.utils.translation import gettext
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.payments.models import MakerspacePaymentSettings, RefundPolicy
from apps.payments.serializers_refund_policies import RefundPolicySerializer

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404)}
#: Who may READ the policy: the people who decide cases under it, and finance.
READ_ACTIONS = (rbac.Action.MANAGE_MAKERSPACE, rbac.Action.VIEW_FINANCE, rbac.Action.MANAGE_EVENTS,
                rbac.Action.MANAGE_BOOKINGS, rbac.Action.MANAGE_MEMBERS)
RULES = ("Events and bookings: cancelling at least `full_before_minutes` before the start refunds in full; at "
         "least `partial_before_minutes` refunds `partial_percent`; later refunds nothing. Memberships: "
         "cancelling within `full_within_days` of the term start refunds in full; then `partial_mode` pro_rata "
         "(unused term time) or percent until the term ends; then nothing. `cancellation_fee` (space currency) "
         "is kept from any refund. Applies to future cancellations only. Audited.")


def _space(actor, makerspace_id, actions=(rbac.Action.MANAGE_MAKERSPACE,)):
    for action in actions:
        space = rbac.scope_by_action(actor, action, servable_queryset(), field="pk").filter(pk=makerspace_id).first()
        if space is not None:
            return space
    raise NotFound(gettext("Makerspace not found."))


def _context(space, area):
    return {"currency": MakerspacePaymentSettings.for_makerspace(space).default_currency, "area": area}


def _plan(space, plan_id):
    from apps.makerspaces.models import MembershipPlan
    return get_object_or_404(MembershipPlan.objects.filter(makerspace=space), pk=plan_id)


def _save(request, space, area, plan=None):
    space = servable_queryset().select_for_update().get(pk=space.pk)
    policy = RefundPolicy.objects.filter(makerspace=space, area=area, plan=plan).first() or RefundPolicy(
        makerspace=space, area=area, plan=plan)
    serializer = RefundPolicySerializer(policy, data=request.data, context=_context(space, area))
    serializer.is_valid(raise_exception=True)
    serializer.save(updated_by=request.user)
    audit.record(request.user, "payment.refund_policy_updated", makerspace=space, target=space,
                 meta={"area": area, "plan_id": plan.pk if plan else None, "fields": sorted(serializer.validated_data)})
    return Response(serializer.data)


def _remove(request, space, area, plan=None):
    policy = get_object_or_404(RefundPolicy.objects.select_for_update(), makerspace=space, area=area, plan=plan)
    policy.delete()
    audit.record(request.user, "payment.refund_policy_updated", makerspace=space, target=space,
                 meta={"area": area, "plan_id": plan.pk if plan else None, "removed": True})
    return Response(status=204)


def _area(area):
    if area not in RefundPolicy.Area.values:
        raise NotFound(gettext("Unknown refund policy area."))
    return area


class RefundPolicyListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Read the refund policy for every area and membership plan",
        description="Requires manage_makerspace, view_finance, manage_events, manage_bookings or manage_members. "
                    "One default row per area (events, bookings, membership), then any per-plan membership rules. "
                    "`configured=false` means no policy: a cancellation owes nothing automatically and staff decide "
                    "each request. A space-cancelled event is always owed in full. " + RULES,
        request=None, responses={200: RefundPolicySerializer(many=True), **ERRORS},
    )
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id, READ_ACTIONS)
        rows = list(RefundPolicy.objects.filter(makerspace=space).select_related("plan").order_by("plan__name", "pk"))
        defaults = {row.area: row for row in rows if row.plan_id is None}
        policies = [defaults.get(area) or RefundPolicy(makerspace=space, area=area) for area in RefundPolicy.Area.values]
        policies += [row for row in rows if row.plan_id is not None]
        return Response(RefundPolicySerializer(policies, many=True, context=_context(space, "")).data)


class RefundPolicyDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Set the default refund policy for one area",
                   description="Requires manage_makerspace. " + RULES,
                   request=RefundPolicySerializer, responses={200: RefundPolicySerializer, **ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id, area):
        return _save(request, _space(request.user, makerspace_id), _area(area))

    @extend_schema(tags=["Payments"], summary="Remove the default refund policy for one area",
                   description="Requires manage_makerspace. Afterwards a cancellation owes nothing automatically "
                               "and staff decide each request. Open cases keep their assessed figure. Audited.",
                   request=None, responses={204: None, **ERRORS})
    @transaction.atomic
    def delete(self, request, makerspace_id, area):
        return _remove(request, _space(request.user, makerspace_id), _area(area))


class RefundPlanPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Set the refund policy for one membership plan",
                   description="Requires manage_makerspace. Overrides the membership default for terms of this "
                               "plan. " + RULES,
                   request=RefundPolicySerializer, responses={200: RefundPolicySerializer, **ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id, plan_id):
        space = _space(request.user, makerspace_id)
        return _save(request, space, RefundPolicy.Area.MEMBERSHIP, _plan(space, plan_id))

    @extend_schema(tags=["Payments"], summary="Remove one membership plan's refund policy",
                   description="Requires manage_makerspace. The plan falls back to the membership default. Audited.",
                   request=None, responses={204: None, **ERRORS})
    @transaction.atomic
    def delete(self, request, makerspace_id, plan_id):
        space = _space(request.user, makerspace_id)
        return _remove(request, space, RefundPolicy.Area.MEMBERSHIP, _plan(space, plan_id))
