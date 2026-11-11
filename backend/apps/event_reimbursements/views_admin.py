"""Screening and finance dispatch have explicit, separately authorized variants."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from .http import PrivateView, body, paginated, admin_event
from . import serializers as s, serializers_finance as f, serializers_read as reads
from .api_schema import ERRORS, TAGS, IDEMPOTENCY, REVIEW, CLAIM_DETAIL, REQUEST_PAGE, FINANCE
from . import programme_workflow, award_workflow, claim_workflow, direct_booking, pools, staff_claims
from . import serializers_hackmoney as hm
from .config_models import ReimbursementProgramme
from .request_models import GrantRequest
from .claim_models import ReimbursementClaim
from .projections import programme_detail, request_detail, claim_detail


class ProgrammeView(PrivateView):
    @extend_schema(tags=TAGS, description=FINANCE, responses={200: reads.ProgrammeFinanceDetail, **ERRORS})
    def get(self, request, pk):
        event, _ = admin_event(request, pk, finance_only=True)
        return Response(programme_detail(ReimbursementProgramme.objects.filter(event=event).first(), finance=True))

    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=f.ProgrammeCreateOrGetCommand,
                   responses={200: s.CommandResult, 201: s.CommandResult, **ERRORS})
    def post(self, request, pk):
        admin_event(request, pk, finance_only=True)
        value = programme_workflow.create_or_get(request=request, event_id=pk, data=body(request, f.ProgrammeCreateOrGetCommand))
        return Response(value, status=201 if value["created"] else 200)

    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=f.ProgrammeFinanceCommand,
                   responses={200: s.CommandResult, **ERRORS})
    def patch(self, request, pk):
        admin_event(request, pk, finance_only=True)
        return Response(programme_workflow.configure(request=request, event_id=pk, data=body(request, f.ProgrammeFinanceCommand)))


class RequestListView(PrivateView):
    @extend_schema(tags=TAGS, responses={200: REQUEST_PAGE, **ERRORS})
    def get(self, request, pk):
        event, finance = admin_event(request, pk)
        return paginated(request, GrantRequest.objects.filter(event=event).exclude(state="draft")
            .order_by("submitted_at", "pk"), lambda row: request_detail(row, sensitive=finance, screening=True))


class AwardDecisionView(PrivateView):
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=f.AwardDecisionCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, pk, request_id):
        event, _ = admin_event(request, pk)
        get_object_or_404(GrantRequest, pk=request_id, event=event)
        return Response(award_workflow.decide(request=request, event_id=pk, request_id=request_id,
            data=body(request, f.AwardDecisionCommand)))


class ClaimListView(PrivateView):
    @extend_schema(tags=TAGS, responses={200: reads.ClaimPage, **ERRORS})
    def get(self, request, pk):
        event, finance = admin_event(request, pk)
        return paginated(request, ReimbursementClaim.objects.filter(event=event).exclude(state__in=("draft", "open"))
            .order_by("submitted_at", "pk"), lambda row: claim_detail(row, finance=finance, detail=False))


class ClaimDetailView(PrivateView):
    @extend_schema(tags=TAGS, responses={200: CLAIM_DETAIL, **ERRORS})
    def get(self, request, pk, claim_id):
        event, finance = admin_event(request, pk)
        row = get_object_or_404(ReimbursementClaim, pk=claim_id, event=event)
        if not finance:
            from apps.payments.event_payouts.errors import require
            require(row.state not in ("draft", "open"), "not_found", status=404)
        return Response(claim_detail(row, finance=finance))


class ClaimReviewView(PrivateView):
    @extend_schema(tags=TAGS, description=FINANCE + " Recommendations require review_reimbursements.",
        parameters=IDEMPOTENCY, request=REVIEW, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, pk, claim_id):
        event, _ = admin_event(request, pk)
        get_object_or_404(ReimbursementClaim, pk=claim_id, event=event)
        data = body(request, f.ClaimReviewCommand)
        if data["mode"] == "recommend":
            return Response(claim_workflow.recommend(event_id=pk, actor=request.user, request=request, claim_id=claim_id, data=data))
        return Response(claim_workflow.decide(request=request, event_id=pk, claim_id=claim_id, data=data))


class ClaimExtendView(PrivateView):
    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=f.ClaimDeadlineCommand,
                   responses={200: s.CommandResult, **ERRORS})
    def post(self, request, pk, claim_id):
        admin_event(request, pk, finance_only=True)
        return Response(claim_workflow.extend(request=request, event_id=pk, claim_id=claim_id, data=body(request, f.ClaimDeadlineCommand)))


class AttendanceAttestView(PrivateView):
    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=f.AttendanceAttestationCommand,
                   responses={201: s.CommandResult, **ERRORS})
    def post(self, request, pk, claim_id):
        admin_event(request, pk, finance_only=True)
        return Response(claim_workflow.attest(request=request, event_id=pk, claim_id=claim_id,
            data=body(request, f.AttendanceAttestationCommand)), status=201)


class ReceiptOverrideView(PrivateView):
    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=f.ReceiptAllocationOverrideCommand,
                   responses={201: s.CommandResult, **ERRORS})
    def post(self, request, pk, claim_id):
        admin_event(request, pk, finance_only=True)
        return Response(claim_workflow.receipt_override(request=request, event_id=pk, claim_id=claim_id,
            data=body(request, f.ReceiptAllocationOverrideCommand)), status=201)


class CorrectDecisionView(PrivateView):
    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=f.CorrectClaimDecisionCommand,
                   responses={200: s.CommandResult, **ERRORS})
    def post(self, request, pk, claim_id):
        admin_event(request, pk, finance_only=True)
        return Response(claim_workflow.decide(request=request, event_id=pk, claim_id=claim_id,
            data=body(request, f.CorrectClaimDecisionCommand), correction=True))


class CrewPoolView(PrivateView):
    """Hack-money G14: finance adds the one crew pool, funded in the same transaction."""
    @extend_schema(tags=TAGS, description=FINANCE + " 409 crew_pool_exists; 404 feature_disabled when events.crew_claims is off.",
                   parameters=IDEMPOTENCY, request=hm.CrewPoolCommand, responses={201: s.CommandResult, **ERRORS})
    def post(self, request, pk):
        admin_event(request, pk, finance_only=True)
        return Response(pools.create_crew_pool(request=request, event_id=pk, data=body(request, hm.CrewPoolCommand)),
                        status=201)


class DirectBookingView(PrivateView):
    """Hack-money G12: record travel the organiser booked; commits the pool and writes a ledger expense."""
    @extend_schema(tags=TAGS, description=FINANCE + " Never sends money: the space already paid the vendor.",
                   parameters=IDEMPOTENCY, request=hm.DirectBookingCommand, responses={200: s.CommandResult, **ERRORS})
    def post(self, request, pk, request_id):
        event, _ = admin_event(request, pk, finance_only=True)
        get_object_or_404(GrantRequest, pk=request_id, event=event)
        return Response(direct_booking.record(request=request, event_id=pk, request_id=request_id,
                                              data=body(request, hm.DirectBookingCommand)))


class DirectBookingCancelView(PrivateView):
    """Hack-money G12: void the booking's ledger expense and release its committed budget."""
    @extend_schema(tags=TAGS, description=FINANCE, parameters=IDEMPOTENCY, request=hm.DirectBookingCancelCommand,
                   responses={200: s.CommandResult, **ERRORS})
    def post(self, request, pk, request_id):
        event, _ = admin_event(request, pk, finance_only=True)
        get_object_or_404(GrantRequest, pk=request_id, event=event)
        return Response(direct_booking.cancel(request=request, event_id=pk, request_id=request_id,
                                              data=body(request, hm.DirectBookingCancelCommand)))


class StaffClaimView(PrivateView):
    """Parity C17: staff file a travel claim for themselves or for a speaker or volunteer."""
    @extend_schema(tags=TAGS, parameters=IDEMPOTENCY, request=hm.StaffClaimCommand,
                   description="Host VIEW_FINANCE or the review_reimbursements grant, and a full browser session. "
                               "The claim becomes a `kind=staff` request funded from the event's pool (crew pool when "
                               "there is one); 409 budget_exhausted when the pool cannot cover it, 409 "
                               "staff_claim_registration_required when the person has no live registration, 404 "
                               "feature_disabled when events.staff_claims is off.",
                   responses={201: s.CommandResult, **ERRORS})
    def post(self, request, pk):
        admin_event(request, pk)
        return Response(staff_claims.file_claim(request=request, event_id=pk, data=body(request, hm.StaffClaimCommand)),
                        status=201)
