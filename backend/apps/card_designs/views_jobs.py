"""Card jobs for a space's member cards, and reading/cancelling/downloading any card job.

Programme and event scopes queue through their own apps' routes with the same service;
reading a job is requester-only (plus the superadmin, who needs a PII window for files).
"""
from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.evidence.responses import storage_unavailable_response
from apps.evidence.storage import StorageUnavailable
from apps.openapi_errors import errors

from . import jobs
from .authority import space_for
from .models import CardJob
from .serializers import CardJobCreateSerializer, CardJobLinkSerializer, CardJobSerializer

TAGS = ["Card jobs"]


def member_card_targets(space, values):
    from apps.makerspaces.models import MemberCard
    rows = MemberCard.objects.filter(makerspace=space)
    if values.get("status", "active") == "active":
        rows = rows.filter(revoked_at__isnull=True, membership__isnull=False)
    if values.get("card_ids"):
        rows = rows.filter(pk__in=values["card_ids"])
    if values.get("plan_id"):
        rows = rows.filter(membership__terms__plan_id=values["plan_id"], membership__terms__status="active")
    if values.get("expiring_within_days"):
        soon = timezone.now() + timedelta(days=values["expiring_within_days"])
        rows = rows.filter(membership__terms__status="active", membership__terms__ends_at__lte=soon)
    return list(rows.order_by("card_number").values_list("pk", flat=True).distinct())


def job_params(values):
    return {"paper": values.get("paper", "a4"), "order": values.get("order", "duplex"),
            "crop_marks": values.get("crop_marks", True)}


class MemberCardJobListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="List my card jobs in this space", request=None,
                   responses={200: CardJobSerializer(many=True), **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        rows = CardJob.objects.filter(makerspace=space, scope="member_cards",
                                      requested_by=request.user).order_by("-created_at")[:20]
        return Response(CardJobSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Queue a bulk job: print sheets, one PDF per person, a ZIP, or emails",
                   description="Runs as a Celery job in chunks; poll its progress. Audited.",
                   request=CardJobCreateSerializer,
                   responses={201: CardJobSerializer, 200: CardJobSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = CardJobCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        params = {"explicit": False} if values["kind"] == "email" else job_params(values)
        design_revision = space.card_designs.filter(domain="member_cards").values_list("published_revision", flat=True)
        job, created = jobs.enqueue(request.user, space, values["kind"], scope="member_cards",
                                    targets=member_card_targets(space, values), params=params,
                                    revision=list(design_revision))
        return Response(CardJobSerializer(job).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CardJobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a card job's progress", request=None,
                   responses={200: CardJobSerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(CardJobSerializer(jobs.get_any(request.user, pk)).data)


class CardJobCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Cancel a card job", request=None,
                   responses={200: CardJobSerializer, **errors(401, 404)})
    def post(self, request, pk):
        return Response(CardJobSerializer(jobs.cancel(request.user, jobs.get_any(request.user, pk))).data)


class CardJobResultView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="A short-lived signed link to the job's file (requester only)", request=None,
                   responses={200: CardJobLinkSerializer, **errors(400, 401, 403, 404, 503)})
    def get(self, request, pk):
        try:
            url = jobs.result_link(request.user, jobs.get_any(request.user, pk))
        except StorageUnavailable:
            return storage_unavailable_response()
        response = Response({"url": url})
        response["Cache-Control"] = "no-store"
        return response
