"""Account-owned request/direct/self-checkout history without a membership dashboard."""
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.accounts.rbac_borrowers import scope_personal_borrowing
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from .member_history_serializers import OwnBorrowingHistorySerializer
from .models import HardwareRequest, HardwareRequestItem
from .return_models import ReturnEvent
from .view_helpers import ERROR_400, ERROR_401, ERROR_403, ERROR_404


class HistoryPeriodSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=("all", "current", "history"), default="all")


class MemberBorrowingHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OwnBorrowingHistorySerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return HardwareRequest.objects.none()
        if getattr(self.request, "api_client", None) or getattr(self.request.user, "_claim_audit_context", None):
            raise PermissionDenied(gettext("Borrowing history requires your own account session."))
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=self.kwargs["makerspace_id"])
        require_module(space, "request_workflow")
        require_feature(space, "loans.enabled")
        query = HistoryPeriodSerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        rows = scope_personal_borrowing(self.request.user, HardwareRequest.objects.all(), makerspace=space)
        closed = [HardwareRequest.Status.REJECTED, HardwareRequest.Status.RETURNED,
                  HardwareRequest.Status.CLOSED_WITH_ISSUE, HardwareRequest.Status.CANCELLED,
                  HardwareRequest.Status.EXPIRED]
        period = query.validated_data["period"]
        if period == "current":
            rows = rows.exclude(status__in=closed)
        elif period == "history":
            rows = rows.filter(status__in=closed)
        return rows.select_related("public_tool_loan").prefetch_related(
            Prefetch("items", queryset=HardwareRequestItem.objects.select_related("product").order_by("id")),
            Prefetch("returnevent_set", queryset=ReturnEvent.objects.filter(makerspace=space).only("id", "request_id", "created_at").order_by("created_at", "id")),
        ).order_by("-created_at", "-id")

    @extend_schema(tags=["Member borrowing"], summary="List my own borrowing requests, handovers and returns",
                   description="Requires a live, unrestricted personal account. No membership or online-payment rail is required. Only the caller's own requests in this servable makerspace are returned, including their merged-account history. Disabled lending is unavailable; private evidence, QR, storage, contact and staff fields are never included.",
                   parameters=[OpenApiParameter("period", str, enum=["all", "current", "history"], required=False)],
                   responses={200: OwnBorrowingHistorySerializer(many=True), 400: ERROR_400,
                              401: ERROR_401, 403: ERROR_403, 404: ERROR_404})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
