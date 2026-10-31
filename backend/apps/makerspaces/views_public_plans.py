"""Public plan cards and per-plan pages (X5), and the invite-link check (X11).

Anonymous reads. Only plans that are listed -- public, active and not archived -- appear,
with their prices (`is_public` is the only listing rule). Off switches answer 404:
`membership.public_plans` for the plans, `membership.admission_tools` for invite links.
The invite check never reveals more than "valid, for this plan" and does not use it up.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.membership_plan_policy import fee_amount, listed_plans, plan_policy
from apps.makerspaces.serializers_membership_l4 import PublicPlanSerializer
from apps.makerspaces.servability import servable_queryset

NOT_FOUND = {404: OpenApiResponse(description="Unknown space, plan or link, or the feature is off.")}


def _space(slug, feature):
    return require_membership_feature(get_object_or_404(servable_queryset(), slug=slug), feature)


def _context(space, plans):
    from apps.makerspaces.membership_admission_settings import settings_for
    base = settings_for(space)
    fees, modes = {}, {}
    for plan in plans:
        amount, _currency = fee_amount(base, plan)
        fees[plan.pk] = amount if amount and amount > 0 else None
        modes[plan.pk] = plan_policy(space, plan, base).join_mode
    return {"fees": fees, "modes": modes}


def _render(space, plans):
    context = _context(space, plans)
    rows = PublicPlanSerializer(plans, many=True, context=context).data
    for row in rows:
        row["join_mode"] = context["modes"][row["id"]]
    return rows


class PublicPlanListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Public memberships"], summary="List a space's public membership plans",
                   responses={200: PublicPlanSerializer(many=True), **NOT_FOUND})
    def get(self, request, makerspace_slug):
        space = _space(makerspace_slug, "public_plans")
        return Response(_render(space, list(listed_plans(space))))


class PublicPlanDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Public memberships"], summary="One public membership plan",
                   responses={200: PublicPlanSerializer, **NOT_FOUND})
    def get(self, request, makerspace_slug, plan_slug):
        space = _space(makerspace_slug, "public_plans")
        plan = get_object_or_404(listed_plans(space), slug=plan_slug)
        return Response(_render(space, [plan])[0])


class PublicInviteLinkView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "membership_request"

    @extend_schema(tags=["Public memberships"], summary="Check a membership invite link",
                   description="Says whether the link can still be used and which plan it is for. "
                               "Does not use it up; joining does.",
                   responses={200: inline_serializer("PublicInviteLink", {
                       "valid": serializers.BooleanField(), "plan_id": serializers.IntegerField(allow_null=True),
                       "plan_name": serializers.CharField(allow_blank=True), "label": serializers.CharField(allow_blank=True),
                   }), **NOT_FOUND})
    def get(self, request, makerspace_slug, code):
        from apps.makerspaces.membership_invite_links import peek
        space = _space(makerspace_slug, "admission_tools")
        link = peek(space, code)
        plan = link.plan if link.plan_id and link.plan.archived_at is None and link.plan.is_active else None
        return Response({"valid": True, "plan_id": plan.pk if plan else None,
                         "plan_name": plan.name if plan else "", "label": link.label})
