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
from . import payout_workflow, payee_workflow, obligation_workflow, eligibility_workflow, exports
from .obligation_models import EventPayoutObligation
from .queries import summary, paid


class FinancePayoutListView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: s.PayoutSummarySerializer(many=True), **s.ERRORS})
    def get(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        authorize(request, space)
        rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE,
            EventPayoutObligation.objects.filter(servable_q("makerspace"), makerspace=space)).order_by("-created_at", "pk")
        return paginate(request, rows, lambda row: summary(obligation(request, row.pk, makerspace_id=makerspace_id)))


class FinancePayoutDetailView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: s.PayoutSummarySerializer, **s.ERRORS})
    def get(self, request, makerspace_id, obligation_id):
        row = obligation(request, obligation_id, makerspace_id=makerspace_id)
        revisions = [{"id": item.pk, "sequence": item.sequence, "kind": item.kind,
            "approved_minor": item.approved_minor, "reason_code": item.reason_code,
            "decision_summary": json.loads(item.decision_summary), "created_at": item.created_at}
            for item in row.revisions.order_by("sequence")]
        return Response({**summary(row), "payee": payee_workflow.projection(payee_workflow.current(row)),
            "revisions": revisions, "entries": list(row.entries.values("id", "amount_minor", "currency", "method",
                "reference", "paid_at", "recorded_at", "recorded_by_id", "amends_id", "is_void", "payee_revision_id"))})


class RecordPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.RecordPayoutCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payout_workflow.record(request=request, obligation_id=obligation_id, data=body(request, f.RecordPayoutCommand)))


class AmendPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.AmendPayoutCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id, entry_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payout_workflow.amend(request=request, obligation_id=obligation_id, entry_id=entry_id,
                                               data=body(request, f.AmendPayoutCommand)))


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
    @extend_schema(tags=["Event payouts"], request=s.RevealCommand, responses={200: s.RevealSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(payee_workflow.reveal(request=request, obligation_id=obligation_id, data=body(request, s.RevealCommand)))


class HoldPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayoutHoldCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(eligibility_workflow.hold(request=request, obligation_id=obligation_id, data=body(request, f.PayoutHoldCommand)))


class ReleaseHoldView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.ReleasePayoutHoldCommand, responses={200: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id, obligation_id):
        obligation(request, obligation_id, makerspace_id=makerspace_id)
        return Response(eligibility_workflow.hold(request=request, obligation_id=obligation_id,
                                                 data=body(request, f.ReleasePayoutHoldCommand), release=True))


class ExportPayoutView(PrivateView):
    @extend_schema(tags=["Event payouts"], request=f.PayoutExportCommand, responses={201: s.PayoutResultSerializer, **s.ERRORS})
    def post(self, request, makerspace_id):
        return Response(exports.create(request=request, makerspace_id=makerspace_id,
                                        data=body(request, f.PayoutExportCommand)), status=201)


class DownloadExportView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: {"type": "string", "format": "binary"}, **s.ERRORS})
    def get(self, request, makerspace_id, batch_id):
        csv = exports.download(request=request, makerspace_id=makerspace_id, batch_id=batch_id)
        return HttpResponse(csv, content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="payout-checklist-{batch_id}.csv"'})


class PayoutDashboardView(PrivateView):
    @extend_schema(tags=["Event payouts"], responses={200: s.PayoutSummarySerializer(many=True), **s.ERRORS})
    def get(self, request, makerspace_id):
        from django.db.models import OuterRef, Subquery, Sum, BigIntegerField, Value
        from django.db.models.functions import Coalesce
        from .payout_models import EventPayoutEntry
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        authorize(request, space)
        tips = EventPayoutEntry.objects.filter(obligation_id=OuterRef("pk"), amended_by__isnull=True,
            is_void=False).order_by().values("obligation_id").annotate(total=Sum("amount_minor")).values("total")
        rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE,
            EventPayoutObligation.objects.filter(makerspace=space)).annotate(
                paid_minor=Coalesce(Subquery(tips), Value(0), output_field=BigIntegerField()))
        return Response({"currencies": list(rows.values("currency").annotate(
            approved_minor=Sum("approved_minor"), paid_minor=Sum("paid_minor")).order_by("currency"))})
