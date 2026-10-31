"""The member's own side of the L4 lifecycle: consent, erasure, history, refund estimate.

Each route answers for the signed-in member's OWN active membership in one space, found
through the rbac tenant boundary, and 404s when `membership` or the route's switch is
off (#95). Nothing here returns staff notes or staff-written reasons.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.schemas_self_service import ACCOUNT_ERRORS as ERRORS
from apps.makerspaces import membership_consent, membership_erasure
from apps.makerspaces.membership_features import require_membership_feature
from apps.makerspaces.membership_history_timeline import timeline
from apps.makerspaces.models import MakerspaceMembership, MembershipErasureRequest
from apps.makerspaces.serializers_membership_l4 import (
    ConsentLedgerSerializer, ConsentPurposeInputSerializer, ErasureInputSerializer, ErasureRequestSerializer,
    RefundSuggestionSerializer, TimelineEntrySerializer,
)


def mine(user, makerspace_id, feature):
    require_member_account(user)
    if not user.is_active or user.access_status != "active" or user.is_walk_in:
        raise PermissionDenied("An active member account is required.")
    rows = rbac.scope_by_makerspace(user, MakerspaceMembership.objects.select_related("makerspace"))
    membership = get_object_or_404(rows, user=user, makerspace_id=makerspace_id, status="active")
    require_membership_feature(membership.makerspace, feature)
    return membership


def _ledger_payload(membership):
    purposes, version = membership_consent.published(membership.makerspace)
    return {"purposes": purposes, "notice_version": version, "consents": membership_consent.ledger(membership)}


class MemberConsentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member account"], summary="Your consent ledger in this space",
                   description="The purposes this space asks consent for, its current notice version, and "
                               "every consent you gave or withdrew. Needs membership.consent.",
                   responses={200: ConsentLedgerSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        return Response(ConsentLedgerSerializer(_ledger_payload(mine(request.user, makerspace_id, "consent"))).data)

    @extend_schema(tags=["Member account"], summary="Give consent for one purpose",
                   description="Stamped with the current notice version. Giving it again while it stands "
                               "changes nothing. Audited as membership.consent_given.",
                   request=ConsentPurposeInputSerializer, responses={200: ConsentLedgerSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        membership = mine(request.user, makerspace_id, "consent")
        data = ConsentPurposeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        membership_consent.give(request.user, membership, data.validated_data["purpose"])
        return Response(ConsentLedgerSerializer(_ledger_payload(membership)).data)

    @extend_schema(tags=["Member account"], summary="Withdraw consent for one purpose",
                   description="Stamps the withdrawal time on the standing consent; the history stays. "
                               "Audited as membership.consent_withdrawn.",
                   request=ConsentPurposeInputSerializer, responses={200: ConsentLedgerSerializer, **ERRORS})
    def delete(self, request, makerspace_id):
        membership = mine(request.user, makerspace_id, "consent")
        data = ConsentPurposeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        membership_consent.withdraw(request.user, membership, data.validated_data["purpose"])
        return Response(ConsentLedgerSerializer(_ledger_payload(membership)).data)


class MemberErasureRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member account"], summary="Your erasure requests in this space",
                   responses={200: ErasureRequestSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        membership = mine(request.user, makerspace_id, "erasure")
        rows = MembershipErasureRequest.objects.filter(membership=membership).order_by("-created_at", "-pk")
        return Response(ErasureRequestSerializer(rows, many=True).data)

    @extend_schema(tags=["Member account"], summary="Ask this space to erase your membership data",
                   description="Staff approve (your data here is anonymised and the membership ends; payment "
                               "records and the audit log are kept) or reject with a note. Your account is "
                               "never deleted. One open request at a time. Audited.",
                   request=ErasureInputSerializer, responses={201: ErasureRequestSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        membership = mine(request.user, makerspace_id, "erasure")
        data = ErasureInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = membership_erasure.request_erasure(request.user, membership, data.validated_data.get("note", ""))
        return Response(ErasureRequestSerializer(row).data, status=201)


class MemberErasureWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member account"], summary="Withdraw your open erasure request",
                   request=None, responses={200: ErasureRequestSerializer, **ERRORS})
    def post(self, request, makerspace_id, request_id):
        membership = mine(request.user, makerspace_id, "erasure")
        row = get_object_or_404(MembershipErasureRequest, pk=request_id, membership=membership)
        return Response(ErasureRequestSerializer(membership_erasure.withdraw(request.user, row)).data)


class MemberHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member account"], summary="Your membership history in words",
                   description="Joins, renewals, extensions, lapses and cancellations, newest first. "
                               "Needs membership.history.",
                   responses={200: TimelineEntrySerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        membership = mine(request.user, makerspace_id, "history")
        return Response(TimelineEntrySerializer(timeline(membership), many=True).data)


class MemberRefundSuggestionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Payments"], summary="What the space's policy suggests for a membership refund",
                   description="X20: the amount the membership refund policy would suggest if you cancelled "
                               "now. Only an estimate; staff decide when you ask. Needs one of your own paid "
                               "membership charges here.",
                   responses={200: RefundSuggestionSerializer, **ERRORS})
    def get(self, request, makerspace_id, payment_id):
        from apps.makerspaces.membership_refund_suggestion import suggestion
        from apps.payments.member_access import member_may_see_own_charges
        from apps.payments.member_scope import member_payment_queryset
        if not member_may_see_own_charges(request.user, makerspace_id):
            raise PermissionDenied("An active membership or an existing charge is required.")
        payment = member_payment_queryset(request.user, makerspace_id).filter(pk=payment_id).first()
        if payment is None:
            raise NotFound("Payment not found.")
        return Response(RefundSuggestionSerializer(suggestion(payment)).data)
