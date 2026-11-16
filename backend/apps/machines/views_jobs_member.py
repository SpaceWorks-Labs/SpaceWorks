"""The member's answers on their own job (#141): approve or decline a quote, resubmit."""

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.machines import service_workflow_review as review
from apps.machines.serializers_jobs import MemberJobSerializer
from apps.machines.views_jobs import ERRORS, _render
from apps.machines.views_service_cancel import _owned, _require_owner_session


class ApproveQuoteSerializer(serializers.Serializer):
    digest = serializers.CharField(max_length=64, help_text="The quote digest the member was shown; a "
                                                            "different one answers 409 price_changed.")


class ResubmitSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=4000, default="")
    file_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=20, default=list)


class _MemberJobAction(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "public_request_submit"

    def job(self, request, pk):
        user = _require_owner_session(request)
        return user, _owned(user, Q(pk=pk))

    def done(self, user, row):
        return Response(_render(_owned(user, Q(pk=row.pk)), user))


class MemberApproveQuoteView(_MemberJobAction):
    @extend_schema(tags=["Member machine service"], summary="Approve the quote on my job",
                   description="Pay-at-completion types join the queue now; prepaid types raise the quoted charge "
                               "and join the queue once it is settled.",
                   request=ApproveQuoteSerializer, responses={200: MemberJobSerializer, **ERRORS})
    def post(self, request, pk):
        user, row = self.job(request, pk)
        payload = ApproveQuoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return self.done(user, review.approve_quote(row, user, digest=payload.validated_data["digest"]))


class MemberDeclineQuoteView(_MemberJobAction):
    @extend_schema(tags=["Member machine service"], summary="Decline the quote (cancels the job, nothing charged)",
                   request=None, responses={200: MemberJobSerializer, **ERRORS})
    def post(self, request, pk):
        user, row = self.job(request, pk)
        return self.done(user, review.decline_quote(row, user))


class MemberResubmitView(_MemberJobAction):
    @extend_schema(tags=["Member machine service"], summary="Send the changes staff asked for",
                   request=ResubmitSerializer, responses={200: MemberJobSerializer, **ERRORS})
    def post(self, request, pk):
        user, row = self.job(request, pk)
        payload = ResubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        return self.done(user, review.resubmit(row, user, note=data["note"], file_ids=data["file_ids"]))
