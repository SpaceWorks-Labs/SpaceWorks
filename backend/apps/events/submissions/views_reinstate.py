"""Parity E-B4 (D7): reinstate a disqualified submission. Mounted from `judging/urls_e_b4.py`."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .moderation import reinstate
from .serializers import CommandSerializer, ErrorSerializer, ProjectResponseSerializer
from .views_base import PrivateSubmissionView

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 413, 423, 429, 503)}


class ReinstateSerializer(CommandSerializer):
    reason = serializers.CharField(max_length=1000)
    stage_id = serializers.IntegerField(min_value=1, required=False,
                                        help_text="The stage to reinstate; omitted means the project's furthest stage.")


class ReinstateResponseSerializer(ProjectResponseSerializer):
    restored_assignments = serializers.IntegerField(help_text="Judging assignments given back to their judges.")
    skipped_assignments = serializers.IntegerField(
        help_text="Invalidated assignments left alone: a finalized or pairwise round, or a judge now in conflict.")


class ReinstateView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ReinstateSerializer, responses={200: ReinstateResponseSerializer, **ERRORS},
                   tags=["Event submissions"],
                   description="Undo a disqualification: the entry is eligible again, its judging assignments "
                               "return (scores were never deleted) and an open entry-fee refund case is voided. "
                               "409 not_disqualified, or fee_refunded once the fee went back to the entrant.")
    def post(self, request, pk, submission_id):
        serializer = ReinstateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(reinstate(actor=request.user, event_id=pk, submission_id=submission_id,
                                  **serializer.validated_data))
