"""Finance ledger: expenses and other receipts (void, never delete), receipts, opening balances.

Every route is scoped per area through `finance_scope` (#100) and answers 404 while the
space's `finance.ledger` switch is off. Recording is always possible through
`ledger_api` from other workflows; these routes are the staff screens.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.local_time import local_now
from apps.payments import ledger_api, ledger_entries
from apps.payments.l5_gates import finance_space
from apps.payments.models_ledger_entries import LedgerEntry
from apps.payments.serializers_ledger import (
    FinanceViewSerializer, LedgerEntryCreateSerializer, LedgerEntryPage, LedgerEntrySerializer,
    OpeningBalanceSerializer, ReceiptUploadRequestSerializer, ReceiptUploadSerializer, ReceiptUrlSerializer,
    VoidSerializer,
)

ERRORS = {400: OpenApiResponse(ErrorSerializer), 401: OpenApiResponse(ErrorSerializer),
          403: OpenApiResponse(ErrorSerializer), 404: OpenApiResponse(ErrorSerializer)}
CONFLICT = OpenApiResponse(ErrorSerializer, description="`ledger_source_conflict`, `ledger_entry_voided`, "
                                                        "`void_reason_required`, `receipt_invalid` or `receipt_in_use`.")
FILTERS = [OpenApiParameter("kind", OpenApiTypes.STR, enum=LedgerEntry.Kind.values),
           OpenApiParameter("domain", OpenApiTypes.STR, enum=LedgerEntry.Domain.values),
           OpenApiParameter("event", OpenApiTypes.INT), OpenApiParameter("include_void", OpenApiTypes.BOOL)]


def _entry(request, makerspace_id, entry_id, view):
    return get_object_or_404(ledger_entries.scoped_entries(request.user, makerspace_id, view), pk=entry_id)


class FinanceAccessView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Which finance areas the caller sees and records",
                   description="404 without any finance area or while `finance.ledger` is off.",
                   responses={200: FinanceViewSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        _space, view = finance_space(request, makerspace_id)
        return Response({"everything": view.everything, "domains": sorted(view.domains),
                         "machine_type_ids": sorted(view.machine_types) if view.machine_types is not None else None,
                         "record_domains": sorted(view.record_domains), "record_everything": view.record_everything})


class LedgerEntryListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="List expenses and other receipts in the caller's areas",
                   description="Space Managers and view_finance see every area; an area manager sees only "
                               "their area (a Machine Manager only their machine types). Void entries are "
                               "listed, marked, unless `include_void=false`.",
                   parameters=FILTERS, responses={200: LedgerEntryPage, **ERRORS})
    def get(self, request, makerspace_id):
        _space, view = finance_space(request, makerspace_id)
        rows = ledger_entries.scoped_entries(request.user, makerspace_id, view).select_related("receipt")
        params = request.query_params
        if params.get("kind") in LedgerEntry.Kind.values:
            rows = rows.filter(kind=params["kind"])
        if params.get("domain") in LedgerEntry.Domain.values:
            rows = rows.filter(domain=params["domain"])
        if (params.get("event") or "").isdigit():
            rows = rows.filter(event_id=int(params["event"]))
        if params.get("include_void", "true").lower() == "false":
            rows = rows.filter(voided_at__isnull=True)
        pager = StaffListPagination()
        return pager.get_paginated_response(
            LedgerEntrySerializer(pager.paginate_queryset(rows, request, view=self), many=True).data)

    @extend_schema(tags=["Finance"], summary="Record an expense or another receipt",
                   description="The area's manager or finance staff (view_finance + record_payment). "
                               "Append-only: correct a mistake by voiding and re-entering. Audited "
                               "`ledger.expense_recorded` / `ledger.entry_created`.",
                   request=LedgerEntryCreateSerializer,
                   responses={201: LedgerEntrySerializer, 409: CONFLICT, **ERRORS})
    def post(self, request, makerspace_id):
        space, view = finance_space(request, makerspace_id)
        payload = LedgerEntryCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        if not view.may_record(data["domain"], data.get("machine_type_id")):
            raise PermissionDenied("You cannot record money in this area.")
        event = None
        if data.get("event_id"):
            from apps.events.models import Event
            event = get_object_or_404(Event.objects.filter(makerspace=space), pk=data["event_id"])
        record = ledger_api.record_expense if data["kind"] == LedgerEntry.Kind.EXPENSE else ledger_api.record_receipt
        entry = record(space, data["domain"], data.get("machine_type_id"), data["amount"], data["currency"],
                       data["method"], data.get("reference", ""), data.get("receipt_id"), "manual", "",
                       request.user, category=data["category"], description=data["description"],
                       entry_date=data["entry_date"], counterparty=data.get("counterparty", ""), event=event)
        return Response(LedgerEntrySerializer(entry).data, status=201)


class LedgerEntryDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Read one ledger entry", responses={200: LedgerEntrySerializer, **ERRORS})
    def get(self, request, makerspace_id, entry_id):
        _space, view = finance_space(request, makerspace_id)
        return Response(LedgerEntrySerializer(_entry(request, makerspace_id, entry_id, view)).data)


class LedgerEntryVoidView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Void a ledger entry with a reason (never deleted)",
                   description="Whoever may record in the entry's area. Audited `ledger.entry_voided`.",
                   request=VoidSerializer, responses={200: LedgerEntrySerializer, 409: CONFLICT, **ERRORS})
    def post(self, request, makerspace_id, entry_id):
        _space, view = finance_space(request, makerspace_id)
        entry = _entry(request, makerspace_id, entry_id, view)
        if not view.may_record(entry.domain, entry.machine_type_id):
            raise PermissionDenied("You cannot void money in this area.")
        payload = VoidSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(LedgerEntrySerializer(ledger_api.void(entry, request.user,
                                                              payload.validated_data["reason"])).data)


class ReceiptUploadView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Get a presigned upload for a receipt photo or PDF",
                   description="JPEG, PNG, WebP or PDF up to EVIDENCE_MAX_BYTES (10 MB default); the presign binds "
                               "the type and size range. Uploads land on the staging key; recording the entry "
                               "promotes the file exactly once (Hard Rule). Needs authority to record in an area.",
                   request=ReceiptUploadRequestSerializer,
                   responses={201: ReceiptUploadSerializer, 503: OpenApiResponse(ErrorSerializer), **ERRORS})
    def post(self, request, makerspace_id):
        from apps.evidence.services_upload import issue_upload
        from apps.evidence.storage import StorageUnavailable

        space, view = finance_space(request, makerspace_id)
        if not (view.record_everything or view.record_domains):
            raise PermissionDenied("You cannot record money in this space.")
        payload = ReceiptUploadRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            _photo, data = issue_upload(space, actor=request.user, evidence_type="receipt",
                                        content_type=payload.validated_data["content_type"],
                                        size_bytes=payload.validated_data.get("size_bytes"))
        except StorageUnavailable:
            return Response({"detail": "File storage is unavailable.", "code": "storage_unavailable"}, status=503)
        return Response(data, status=201)


class ReceiptUrlView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="A short-lived link to an entry's receipt (photo or PDF)",
                   responses={200: ReceiptUrlSerializer, 503: OpenApiResponse(ErrorSerializer), **ERRORS})
    def get(self, request, makerspace_id, entry_id):
        from apps.evidence.storage import StorageUnavailable, presigned_get_url

        _space, view = finance_space(request, makerspace_id)
        entry = _entry(request, makerspace_id, entry_id, view)
        if entry.receipt_id is None:
            return Response({"detail": "This entry has no receipt.", "code": "receipt_missing"}, status=404)
        try:
            return Response({"url": presigned_get_url(entry.receipt.object_key)})
        except StorageUnavailable:
            return Response({"detail": "File storage is unavailable.", "code": "storage_unavailable"}, status=503)


class OpeningBalanceView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Finance"], summary="Opening cash and bank balances for one financial year",
                   description="Finance staff (view_finance). `fy` is any date inside the year (default today).",
                   parameters=[OpenApiParameter("fy", OpenApiTypes.DATE)],
                   responses={200: OpeningBalanceSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space, view = finance_space(request, makerspace_id)
        if not view.everything:
            raise PermissionDenied("Opening balances are for finance staff.")
        on = OpeningBalanceSerializer().fields["fy_start"].to_internal_value(request.query_params["fy"]) \
            if request.query_params.get("fy") else local_now(space).date()
        rows = ledger_entries.opening_balances(space.pk, ledger_entries.fy_for(space, on))
        return Response(OpeningBalanceSerializer(rows, many=True).data)

    @extend_schema(tags=["Finance"], summary="Set the opening balances for one financial year and currency",
                   description="Finance staff (view_finance + record_payment). Appends a revision; the newest is "
                               "the balance. Audited `ledger.opening_balance_set`.",
                   request=OpeningBalanceSerializer, responses={200: OpeningBalanceSerializer, **ERRORS})
    def put(self, request, makerspace_id):
        space, view = finance_space(request, makerspace_id)
        if not view.record_everything:
            raise PermissionDenied("Opening balances are set by finance staff.")
        payload = OpeningBalanceSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        row = ledger_entries.set_opening_balance(
            actor=request.user, makerspace=space, fy_start_date=data["fy_start"], currency=data["currency"],
            cash_amount=data["cash_amount"], bank_amount=data["bank_amount"])
        return Response(OpeningBalanceSerializer(row).data)
