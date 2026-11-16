"""Staff ID cards: the staff list with card state, issue, bulk issue, reissue and revoke (O-B4 part 2).

Routes under /api/v1/admin/. Needs `MANAGE_MEMBER_CARDS` (or `MANAGE_STAFF`) in the space and the switch
`membership.staff_cards`. Every write is audited by `staff_card_services`.
"""
from django.db.models import Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.makerspaces.models import MakerspaceMembership
from apps.openapi_errors import errors

from . import staff_card_services as services
from .models_staff_cards import StaffCard
from .serializers_staff_cards import (StaffCardBulkIssueSerializer, StaffCardBulkResultSerializer,
                                      StaffCardHolderSerializer, StaffCardIssueSerializer, StaffCardReasonSerializer,
                                      StaffCardSummarySerializer)
from .staff_card_access import card_for, card_row, holder_row, space_for

TAGS = ["Staff ID cards"]


class StaffCardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class StaffCardListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Active staff with their staff-card state (paginated)",
                   description="One row per active staff membership of the space; `card` is the live card or the "
                               "latest revoked one. Query `q` filters by name; `card=none|live` by card state.",
                   request=None, responses={200: StaffCardHolderSerializer(many=True), **errors(401, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        rows = MakerspaceMembership.staff_tracks.filter(makerspace=space, status="active").select_related(
            "user", "assigned_role").prefetch_related(
            "additional_roles__role",
            Prefetch("staff_cards", queryset=StaffCard.objects.order_by("-issued_at", "-pk"), to_attr="_cards"))
        query = (request.query_params.get("q") or "").strip()
        if query:
            rows = rows.filter(Q(user__display_name__icontains=query) | Q(user__username__icontains=query))
        state = request.query_params.get("card")
        if state == "none":
            rows = rows.exclude(staff_cards__revoked_at__isnull=True)
        elif state == "live":
            rows = rows.filter(staff_cards__revoked_at__isnull=True)
        paginator = StaffCardPagination()
        page = paginator.paginate_queryset(rows.order_by("user__display_name", "pk").distinct(), request)
        data = []
        for membership in page:
            cards = membership._cards
            card = next((c for c in cards if c.is_active), cards[0] if cards else None)
            data.append(holder_row(membership, card))
        return paginator.get_paginated_response(data)

    @extend_schema(tags=TAGS, summary="Issue a staff card to one staff member",
                   description="409 `extra_quota_reached` when `staff_cards_issued_monthly` is used up; 400 when the "
                               "person already holds a card or is not an active staff member.",
                   request=StaffCardIssueSerializer,
                   responses={201: StaffCardSummarySerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = StaffCardIssueSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        membership = MakerspaceMembership.staff_tracks.filter(
            makerspace=space, pk=data.validated_data["membership_id"]).first()
        if membership is None:
            from django.http import Http404
            raise Http404()
        card = services.issue(request.user, membership)
        return Response(card_row(card), status=status.HTTP_201_CREATED)


class StaffCardBulkIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Issue staff cards to many staff members at once",
                   description="Each person is issued independently; refusals come back in `skipped` with a reason.",
                   request=StaffCardBulkIssueSerializer,
                   responses={200: StaffCardBulkResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = StaffCardBulkIssueSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.bulk_issue(request.user, space.pk, list(dict.fromkeys(data.validated_data["membership_ids"])))
        return Response({"issued": [card_row(card) for card in result["issued"]], "skipped": result["skipped"]})


class StaffCardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a staff card", request=None,
                   responses={200: StaffCardSummarySerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(card_row(card_for(request.user, pk)))


class StaffCardReissueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Reissue a staff card (same number, new check QR)",
                   description="The old printed card now verifies as revoked (\"a newer card was issued\").",
                   request=None, responses={200: StaffCardSummarySerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        card = card_for(request.user, pk)
        return Response(card_row(services.reissue(request.user, card)))


class StaffCardRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Revoke a staff card", request=StaffCardReasonSerializer,
                   responses={200: StaffCardSummarySerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        card = card_for(request.user, pk)
        data = StaffCardReasonSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        return Response(card_row(services.revoke(request.user, card, reason=data.validated_data["reason"])))
