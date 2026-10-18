"""Finance reads and record-only commands, mounted independently of the rail."""
import json
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_q
from .http import PrivateView, obligation, body, paginate
from .authority import authorize
from . import serializers as s, serializers_finance as f
from . import serializers_responses as r
from . import payout_workflow, payee_workflow, obligation_workflow, eligibility_workflow, exports
from .obligation_models import EventPayoutObligation
from .queries import summary


class FinancePayoutListView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: r.PayoutPage, **s.ERRORS})
    def get(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        authorize(request, space)
        rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE,
            EventPayoutObligation.objects.filter(servable_q("makerspace"), makerspace=space)).order_by("-created_at", "pk")
        return paginate(request, rows, lambda row: summary(obligation(request, row.pk, makerspace_id=makerspace_id), request=request))


class FinancePayoutDetailView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: r.FinancePayoutDetail, **s.ERRORS})
    def get(self, request, makerspace_id, obligation_id):
        row = obligation(request, obligation_id, makerspace_id=makerspace_id)
        revisions = [{"id": item.pk, "sequence": item.sequence, "kind": item.kind,
            "approved_minor": item.approved_minor, "reason_code": item.reason_code,
            "cancellation_note": item.cancellation_note,
            "decision_summary": json.loads(item.decision_summary), "created_at": item.created_at}
            for item in row.revisions.order_by("sequence")]
        return Response({**summary(row, request=request), "payee": payee_workflow.projection(payee_workflow.current(row)),
            "holds": list(row.hold_history.values("id", "kind", "action", "releases_id", "reason_code", "hold_until")),
            "eligibility_history": list(row.eligibility_history.values("id", "evidence_revision", "evidence", "status", "reason_code",
                "acknowledged_by_id", "acknowledged_at")),
            "revisions": revisions, "entries": list(row.entries.values("id", "amount_minor", "currency", "method",
                "reference", "paid_at", "recorded_at", "recorded_by_id", "amends_id", "is_void", "payee_revision_id"))})


class RecordPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayoutRecordCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payout_workflow.record(request=request, obligation_id=obligation_id, data=body(request, f.PayoutRecordCommand)))


class AmendPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayoutAmendCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, entry_id):
        from .payout_models import EventPayoutEntry
        entry = get_object_or_404(EventPayoutEntry, pk=entry_id, obligation__makerspace_id=makerspace_id)
        obligation_id = entry.obligation_id
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payout_workflow.amend(request=request, obligation_id=obligation_id, entry_id=entry_id,
                                               data=body(request, f.PayoutAmendCommand)))


class CancelPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.CancelUnpaidObligationCommand,
                   responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(obligation_workflow.cancel_unpaid(request=request, obligation_id=obligation_id,
                                                          data=body(request, f.CancelUnpaidObligationCommand)))


class VerifyPayeeView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayeeVerifyCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payee_workflow.review(request=request, obligation_id=obligation_id,
                                               data=body(request, f.PayeeVerifyCommand), verified=True))


class CorrectPayeeView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayeeCorrectionCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payee_workflow.review(request=request, obligation_id=obligation_id,
                                               data=body(request, f.PayeeCorrectionCommand), verified=False))


class RevealPayeeView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=s.PayeeRevealCommand, responses={200: s.RevealSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payee_workflow.reveal(request=request, obligation_id=obligation_id, data=body(request, s.PayeeRevealCommand)))


class HoldPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayoutHoldCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(eligibility_workflow.hold(request=request, obligation_id=obligation_id, data=body(request, f.PayoutHoldCommand)))


class ReleaseHoldView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayoutHoldReleaseCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(eligibility_workflow.hold(request=request, obligation_id=obligation_id,
                                                 data=body(request, f.PayoutHoldReleaseCommand), release=True))


class AcknowledgeEligibilityView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.EligibilityAcknowledgementCommand,
                   responses={200: r.EligibilityResult, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(eligibility_workflow.acknowledge(request=request, obligation_id=obligation_id,
            data=body(request, f.EligibilityAcknowledgementCommand)))


class ExportPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.MaskedPayoutExportCommand, responses={201: r.MaskedPayoutBatchDetail, **s.ERRORS})
    def post(self, request, makerspace_id):
        return Response(exports.create(request=request, makerspace_id=makerspace_id,
                                        data=body(request, f.MaskedPayoutExportCommand)), status=201)


class DownloadExportView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: {"type": "string", "format": "binary"}, **s.ERRORS})
    def get(self, request, makerspace_id, batch_id):
        from .errors import require
        require(not request.query_params, "invalid_fields", status=400)
        csv = exports.download(request=request, makerspace_id=makerspace_id, batch_id=batch_id)
        return HttpResponse(csv, content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="payout-checklist-{batch_id}.csv"'})


class PayoutDashboardView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: r.FinanceDashboard, **s.ERRORS})
    def get(self, request, makerspace_id):
        from .dashboard import project
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        authorize(request, space)
        return Response(project(space))
