"""L21b HTTP adapters: finalists, progress, score-next, programme options and prize payouts.

Every write delegates to its workflow, which holds the event lock, the command receipt and the audit.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.response import Response

from apps.payments.payout_session import require_full_session
from . import finalists, options, payouts, progress
from .api_common import ERRORS, PrivateView, admin_event, paginated, schema
from .models_finalists import FinalistAdvance
from .serializers import CommandInput, ResultEnvelope
from .serializers_l21b import (
    FinalistAdvanceRead, FinalistApplyInput, FinalistPreviewRead, FinalistPublishInput, NextProjectRead,
    OptionsInput, OptionsRead, PayoutInput, PayoutRead, PrizePayableAwardRead, PrizePayoutPage, PayoutReverseInput, ProgressRead,
)

PREVIEW_PARAMS = [OpenApiParameter(name, kind, OpenApiParameter.QUERY, required=required) for name, kind, required in (
    ("source_round_id", int, True), ("target_round_id", int, True), ("selection", str, True),
    ("top_n", int, False), ("snapshot_ids", str, False))]


class FinalistPreview(PrivateView):
    @extend_schema(tags=["Event programme judging"], parameters=PREVIEW_PARAMS, responses={200: FinalistPreviewRead, **ERRORS},
                   description="Top N (ties at the cutoff included) or hand-picked finalists from a finalized round. "
                               "Writes nothing; apply sends the fingerprint back. snapshot_ids is comma-separated.")
    def get(self, request, pk):
        params = {key: request.query_params.get(key) for key in ("source_round_id", "target_round_id", "selection", "top_n")
                  if request.query_params.get(key) not in (None, "")}
        ids = request.query_params.get("snapshot_ids")
        if ids:
            params["snapshot_ids"] = [int(value) for value in ids.split(",") if value.strip().isdigit()]
        return Response(FinalistPreviewRead(finalists.preview(pk, actor=request.user, params=params)).data)



class FinalistList(PrivateView):
    @schema(response=FinalistAdvanceRead(many=True), page=True)
    def get(self, request, pk):
        event = admin_event(request, pk)
        from .feature import FINALISTS, require_capability
        require_capability(event, FINALISTS)
        rows = FinalistAdvance.objects.filter(event=event).select_related("target_round").order_by("-pk")
        return paginated(request, [finalists.projection(row) for row in rows], FinalistAdvanceRead)


class FinalistApply(PrivateView):
    @schema(request=FinalistApplyInput, response=FinalistPreviewRead,
            description="Advance the previewed finalists into a draft round, under the event lock; "
                        "409 plan_changed when the preview is stale.")
    def post(self, request, pk):
        result = finalists.apply(pk, actor=request.user, data=request.data)
        return Response({key: value for key, value in result.items() if key != "id"})


class FinalistPublish(PrivateView):
    @schema(request=FinalistPublishInput, response=ResultEnvelope,
            description="Publish the round's current finalists once; the finalists email follows the event switch.")
    def post(self, request, pk):
        return Response(finalists.publish(pk, actor=request.user, data=request.data))


class RoundProgress(PrivateView):
    @schema(response=ProgressRead, description="Below-target projects, per-judge completion, outliers "
            "(over 2 SD from the project mean, or over 25 points apart on a 0-100 scale) and drafts saved "
            "but not submitted for over 24 hours.")
    def get(self, request, pk, round_id):
        return Response(ProgressRead(progress.report(pk, round_id, actor=request.user)).data)


class NextProject(PrivateView):
    @schema(request=CommandInput, response=NextProjectRead,
            description="The judge's started project, else the eligible project with the fewest reviews "
                        "(expected_version is not checked; judges send 0). "
                        "With round visibility 'all' an unassigned project may be pulled and assigned.")
    def post(self, request, pk, round_id):
        return Response(progress.next_project(pk, round_id, actor=request.user, data=request.data))


@extend_schema_view(get=schema(response=OptionsRead),
                    patch=schema(request=OptionsInput, response=OptionsRead,
                                 description="Email switches (off for new events), refund on disqualification, "
                                             "and the entry and team fees (each behind its capability)."))
class ProgrammeOptions(PrivateView):
    http_method_names = ["get", "patch", "head", "options"]

    def get(self, request, pk):
        return Response(options.read(pk, actor=request.user))

    def patch(self, request, pk):
        return Response(options.update(pk, actor=request.user, data=request.data))


class ResultsSendEmail(PrivateView):
    @schema(request=CommandInput, response=OptionsRead,
            description="Send the results email once for the published results, even with the switch off; "
                        "expected_version is the published result's version. 409 already_sent.")
    def post(self, request, pk):
        return Response(options.send_results_email(pk, actor=request.user, data=request.data))


@extend_schema_view(get=schema(response=PrizePayoutPage),
                    post=schema(request=PayoutInput, response=PayoutRead, status=201,
                                description="Record a prize payout by hand (record_payment or the Event Manager); "
                                            "writes one L5 ledger expense. Never moves money."))
class PrizePayouts(PrivateView):
    def get(self, request, pk):
        require_full_session(request)  # 224(c): prize payouts are payee money, session-only
        rows, awards = payouts.listing(pk, actor=request.user)
        return paginated(request, rows, PayoutRead, awards=PrizePayableAwardRead(awards, many=True).data)

    def post(self, request, pk):
        return Response(payouts.record_payout(pk, actor=request.user, data=request.data), status=201)


class PrizePayoutReverse(PrivateView):
    @schema(request=PayoutReverseInput, response=PayoutRead,
            description="Append a reversal row and void the payout's ledger expense.")
    def post(self, request, pk, payout_id):
        return Response(payouts.reverse_payout(pk, payout_id, actor=request.user, data=request.data))
