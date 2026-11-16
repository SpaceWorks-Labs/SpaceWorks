"""Staff routes: a loan's damaged return lines, their repairs, and the handoff itself.

Both answer 404 while `inventory.repairs` is off (no handoff option; the return is long
done and unaffected) and 403 `out_of_scope` to staff who neither manage items nor review
requests (`accept_request`); a reviewer may hand off but reads no repair detail. Every row
is read through the actor's makerspace scope first.
"""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from . import loan_handoff
from .serializers_loan_handoff import (
    LoanRepairHandoffResultSerializer, LoanRepairHandoffSerializer, LoanRepairsSerializer,
)
from .views_common import ERRORS, TAGS, space_for


def _issues(lines):
    from apps.maintenance.models import IssueEvent, IssueReport, RepairPart
    return {row.return_line_id: row for row in IssueReport.objects.filter(return_line__in=lines)
            .select_related("work_order__machine", "work_order__product", "work_order__asset", "work_order__space")
            .prefetch_related(Prefetch("parts", queryset=RepairPart.objects.order_by("created_at", "id")),
                              Prefetch("events", queryset=IssueEvent.objects.filter(kind="payout")))}


def _to_buy(actor, space, issues):
    from apps.procurement import access
    from apps.procurement.models import ToBuyItem
    ids = {part.to_buy_item_id for issue in issues for part in issue.parts.all() if part.to_buy_item_id}
    if not ids:
        return {}
    rows = access.scope_items(ToBuyItem.objects.filter(pk__in=ids), actor, space.pk)
    return {row.pk: row for row in rows.select_related("machine_type", "created_by", "purchaser")
            .prefetch_related("receipts__uploaded_by")}


def _payload(lines, issues, *, detail):
    out = []
    for line in lines:
        asset = loan_handoff.damaged_asset(line)
        product = line.request_item.product if line.request_item_id else None
        out.append({"accountability_id": line.pk, "request_item_id": line.request_item_id,
                    "product_name": getattr(product, "name", ""), "quantity": line.quantity,
                    "asset_id": getattr(asset, "pk", None), "asset_tag": getattr(asset, "asset_tag", ""),
                    "remark": loan_handoff.return_remark(line), "evidence_id": line.evidence_photo_id,
                    "handed_off": line.pk in issues, "issue": issues.get(line.pk) if detail else None})
    return out


def _context(request, space, lines):
    issues = _issues(lines)
    detail = loan_handoff.is_manager(request.user, space)  # reviewers see only that a repair exists
    context = {"request": request, "to_buy": _to_buy(request.user, space, issues.values()) if detail else {}}
    return _payload(lines, issues, detail=detail), context


def _loans(actor, space):
    """The item manager reads every loan of the space; a request reviewer only the loans
    whose source they act on (a direct or self-checkout loan needs that source's action)."""
    from apps.hardware_requests.models import HardwareRequest
    if loan_handoff.is_manager(actor, space):
        return HardwareRequest.objects.filter(makerspace=space)
    from apps.hardware_requests.loan_context_access import authorized_request_queryset
    return authorized_request_queryset(actor, space)


class LoanRepairsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A loan's damaged return lines and their repairs (parts, To-Buy, cost)",
                   responses={200: LoanRepairsSerializer, **ERRORS})
    def get(self, request, makerspace_id, request_id):
        from apps.hardware_requests.models import HardwareRequest
        space = space_for(request.user, makerspace_id)
        loan_handoff.require_manager(request.user, space)
        loan = get_object_or_404(_loans(request.user, space), pk=request_id)
        lines, context = _context(request, space, list(loan_handoff.damaged_lines(space, loan.pk)))
        return Response(LoanRepairsSerializer({"request_id": loan.pk, "lines": lines}, context=context).data)

    @extend_schema(tags=TAGS, summary="Hand a damaged return line off to repairs (idempotent per line)",
                   description="A linked loan-to-repair write: requires a staff session, never a bearer token "
                               "or API client.",
                   request=LoanRepairHandoffSerializer, auth=[{"jwtAuth": []}],
                   responses={201: LoanRepairHandoffResultSerializer, 200: LoanRepairHandoffResultSerializer,
                              **ERRORS})
    def post(self, request, makerspace_id, request_id):
        # Decision 216 item 18: linked mutations are session-only (reads stay token-readable).
        if getattr(request, "api_client", None) or getattr(request, "person_credential", None):
            raise PermissionDenied(gettext("This endpoint requires a staff session."))
        space = space_for(request.user, makerspace_id)
        loan_handoff.require_manager(request.user, space)
        body = LoanRepairHandoffSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        line_id = body.validated_data["accountability_id"]
        get_object_or_404(_loans(request.user, space), pk=request_id)
        line = get_object_or_404(loan_handoff.damaged_lines(space, request_id), pk=line_id)
        issue, created = loan_handoff.hand_off(request.user, space, line.pk, note=body.validated_data["note"])
        lines, context = _context(request, space, [line])
        data = LoanRepairHandoffResultSerializer(
            {"created": created, "issue_id": issue.pk, "line": lines[0]}, context=context).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
