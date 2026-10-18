"""Owner commands use canonical subjects; HTTP never mutates model state."""
from uuid import UUID
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.response import Response
from apps.payments.event_payouts.errors import require
from .http import PrivateView, body, member_event
from . import serializers as s, serializers_read as reads
from .api_schema import ERRORS, TAGS, IDEMPOTENCY
from . import request_workflow, award_workflow, claim_workflow
from .projections import member_summary, claim_detail
from .claim_models import ReimbursementClaim


class ReimbursementView(PrivateView):
    @extend_schema(tags=TAGS, parameters=[OpenApiParameter("creation_operation_id", UUID)],
                   responses={200: reads.MemberSummary, **ERRORS})
    def get(self, request, makerspace_id, pk):
        event = member_event(request, pk, makerspace_id)
        if "creation_operation_id" in request.query_params:
            try:
                UUID(request.query_params["creation_operation_id"])
            except ValueError:
                require(False, "invalid_operation_id", status=400)
        return Response(member_summary(event, request.user))

    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.Command, responses={201: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(request_workflow.create_draft(event_id=pk, actor=request.user, request=request,
            data=body(request, s.Command)), status=201)


class RequestSubmitView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.RequestSubmitCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(request_workflow.submit(event_id=pk, actor=request.user, request=request,
            data=body(request, s.RequestSubmitCommand)))


class RequestWithdrawView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.Command, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(request_workflow.withdraw(event_id=pk, actor=request.user, request=request, data=body(request, s.Command)))


class AwardAcceptView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.AwardResponseCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(award_workflow.respond(event_id=pk, actor=request.user, request=request,
            data=body(request, s.AwardResponseCommand), accept=True))


class AwardDeclineView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.AwardResponseCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(award_workflow.respond(event_id=pk, actor=request.user, request=request,
            data=body(request, s.AwardResponseCommand), accept=False))


class ClaimView(PrivateView):
    @extend_schema(tags=TAGS, responses={200: reads.ClaimFinanceDetail, **ERRORS})
    def get(self, request, makerspace_id, pk):
        event = member_event(request, pk, makerspace_id)
        row = get_object_or_404(ReimbursementClaim, event=event, member=request.user)
        return Response(claim_detail(row, owner=True))

    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ClaimDraftCommand, responses={200: s.CommandResult, **ERRORS})
    def put(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(claim_workflow.save_draft(event_id=pk, actor=request.user, request=request,
            data=body(request, s.ClaimDraftCommand)))


class ClaimSubmitView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ClaimSubmitCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(claim_workflow.submit(event_id=pk, actor=request.user, request=request,
            data=body(request, s.ClaimSubmitCommand)))


class ClaimAppealView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=s.ClaimAppealCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, makerspace_id, pk):
        member_event(request, pk, makerspace_id)
        return Response(claim_workflow.appeal(event_id=pk, actor=request.user, request=request,
            data=body(request, s.ClaimAppealCommand)))
