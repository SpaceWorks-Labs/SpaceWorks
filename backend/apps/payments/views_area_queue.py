"""Decision 242(a)(b): the own-area Payments queue and the owner's claim, pay-link and reminder actions.

Reads/writes admit the actor only for charges `area_queue.area_payments` returns, which is the same subject
authority `reconcile_payments` re-checks. Settling and waiving reuse the existing mark-offline / waive /
bulk routes (no new `record_payment` grant); maker-checker still needs a second `record_payment` holder.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.payments import area_queue, offline_claims, pay_links
from apps.payments.l5_gates import require_capability
from apps.payments.models import ManualSettlement, Payment, PaymentClaim
from apps.payments.payment_rows_l5 import staff_row_context
from apps.payments.reconciliation import with_refunds
from apps.payments.serializers_l5 import ClaimPageSerializer, DecisionNoteSerializer, StaffClaimSerializer
from apps.payments.serializers_reconciliation import PaymentReconciliationSerializer
from apps.payments.subjects import resolve_subject_labels
from apps.payments.views_pay_links import PayLinkCreateSerializer, PayLinkSerializer

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404, 409)}


class AreaQueueRowSerializer(PaymentReconciliationSerializer):
    area = serializers.SerializerMethodField()
    member_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta(PaymentReconciliationSerializer.Meta):
        fields = (*PaymentReconciliationSerializer.Meta.fields, "area", "member_id")
        read_only_fields = fields

    def get_area(self, payment) -> str:
        return area_queue.area_of(payment.subject_type)


class AreaQueueGroupSerializer(serializers.Serializer):
    area = serializers.ChoiceField(choices=area_queue.AREAS)
    pending = serializers.IntegerField()
    overdue = serializers.IntegerField()
    claims = serializers.IntegerField(help_text="Open 'I paid' claims waiting on the owner.")
    owed = serializers.DictField(child=serializers.CharField(), help_text="Amount owed per currency, never summed.")


class AreaQueueSummarySerializer(serializers.Serializer):
    groups = AreaQueueGroupSerializer(many=True)


def _space(request, makerspace_id):
    space = get_object_or_404(servable_queryset(), pk=makerspace_id)
    if area_queue.owned_subject_types(request.user, space.pk) == []:
        raise NotFound()  # owns no charge type here: the queue does not exist for this actor
    return space


QUEUE_ORDERINGS = {"due_at": None, "created_at": "created_at", "-created_at": "-created_at",
                   "amount": "amount", "-amount": "-amount"}


class AreaQueueListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="My own-area charges (pending and owed queue)",
        description=("Every charge the caller owns by subject authority (decision 242): job charges, sessions, loans, "
                     "all event charge types, bookings, shop. Finance staff see every domain; donations never reach an "
                     "area manager. Settle and waive with the existing mark-offline / waive routes."),
        parameters=[
            OpenApiParameter("area", OpenApiTypes.STR, enum=list(area_queue.AREAS)),
            OpenApiParameter("status", OpenApiTypes.STR, enum=[*Payment.Status.values, "all"],
                             description="Default: pending. `all` lists every status."),
            OpenApiParameter("ordering", OpenApiTypes.STR, enum=list(QUEUE_ORDERINGS),
                             description="Default: due_at (soonest due first, undated last)."),
            OpenApiParameter("subject_type", OpenApiTypes.STR, enum=Payment.SubjectType.values),
            OpenApiParameter("due_state", OpenApiTypes.STR, enum=["overdue", "due_today", "upcoming"]),
        ],
        responses={200: AreaQueueRowSerializer(many=True), **ERRORS},
    )
    def get(self, request, makerspace_id):
        from apps.payments.due_dates import filter_due, order_by_due

        space = _space(request, makerspace_id)
        params = request.query_params
        area = params.get("area") if params.get("area") in area_queue.AREAS else None
        wanted = params.get("status") or Payment.Status.PENDING
        rows = area_queue.area_payments(
            request.user, space.pk, area=area, status=None if wanted == "all" else wanted,
            subject_type=params.get("subject_type") if params.get("subject_type") in Payment.SubjectType.values else None)
        if params.get("due_state") in ("overdue", "due_today", "upcoming"):
            rows = filter_due(rows, space, params["due_state"])
        pager = StaffListPagination()
        ordering = params.get("ordering")
        ordered = (with_refunds(rows).order_by(QUEUE_ORDERINGS[ordering], "pk") if QUEUE_ORDERINGS.get(ordering)
                   else order_by_due(with_refunds(rows)))
        page = pager.paginate_queryset(ordered, request, view=self)
        context = {"payment_subject_labels": resolve_subject_labels(page),
                   "payment_settlements": ManualSettlement.effective_for_many(page),
                   "payment_l5": staff_row_context(page)}
        return pager.get_paginated_response(AreaQueueRowSerializer(page, many=True, context=context).data)


class AreaQueueSummaryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Own-area money waiting, grouped by area",
                   responses={200: AreaQueueSummarySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        return Response({"groups": area_queue.summary(request.user, space)})


class AreaClaimListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Members' 'I paid' claims on my own-area charges",
                   parameters=[OpenApiParameter("status", OpenApiTypes.STR, enum=PaymentClaim.Status.values),
                               OpenApiParameter("area", OpenApiTypes.STR, enum=list(area_queue.AREAS),
                                                description="Only claims on this area's charges.")],
                   responses={200: ClaimPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        require_capability(space, "billing.offline_claims")
        area = request.query_params.get("area")
        mine = area_queue.area_payments(request.user, space.pk, area=area if area in area_queue.AREAS else None).values("pk")
        rows = PaymentClaim.objects.filter(makerspace_id=space.pk, payment__in=mine).select_related("payment")
        status = request.query_params.get("status")
        rows = rows.filter(status=status) if status in PaymentClaim.Status.values else rows.filter(
            status__in=PaymentClaim.OPEN_STATUSES)
        pager = StaffListPagination()
        page = pager.paginate_queryset(rows.order_by("-pk"), request, view=self)
        return pager.get_paginated_response(StaffClaimSerializer(page, many=True).data)


class _ClaimDecision(APIView):
    permission_classes = [IsActiveStaff]

    def claim_in_queue(self, request, makerspace_id, claim_id):
        space = _space(request, makerspace_id)
        require_capability(space, "billing.offline_claims")
        claim = PaymentClaim.objects.filter(pk=claim_id, makerspace_id=space.pk).select_related("payment").first()
        if claim is None or area_queue.in_queue(request.user, space.pk, claim.payment_id) is None:
            raise NotFound()
        return claim


class AreaClaimConfirmView(_ClaimDecision):
    @extend_schema(tags=["Payments"], summary="Confirm a claim on my own-area charge",
                   description=("Writes the ManualSettlement receipt through the same service as the finance queue; with "
                                "maker-checker on it is proposed for a second `record_payment` holder instead. Audited."),
                   request=None, responses={200: StaffClaimSerializer, **ERRORS})
    def post(self, request, makerspace_id, claim_id):
        claim = self.claim_in_queue(request, makerspace_id, claim_id)
        return Response(StaffClaimSerializer(offline_claims.confirm_claim(
            actor=request.user, makerspace_id=claim.makerspace_id, claim_id=claim.pk)).data)


class AreaClaimRejectView(_ClaimDecision):
    @extend_schema(tags=["Payments"], summary="Reject a claim on my own-area charge",
                   request=DecisionNoteSerializer, responses={200: StaffClaimSerializer, **ERRORS})
    def post(self, request, makerspace_id, claim_id):
        claim = self.claim_in_queue(request, makerspace_id, claim_id)
        payload = DecisionNoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(StaffClaimSerializer(offline_claims.reject_claim(
            actor=request.user, makerspace_id=claim.makerspace_id, claim_id=claim.pk,
            note=payload.validated_data["note"])).data)


class AreaPayLinkView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Create a pay link for my own-area account-less charge",
                   request=PayLinkCreateSerializer,
                   responses={201: PayLinkSerializer, **ERRORS})
    def post(self, request, makerspace_id, payment_id):
        space = _space(request, makerspace_id)
        require_capability(space, "billing.pay_links")
        if area_queue.in_queue(request.user, space.pk, payment_id) is None:
            raise NotFound()
        payload = PayLinkCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        link, token = pay_links.create_link(actor=request.user, makerspace_id=space.pk, payment_id=payment_id,
                                            **payload.validated_data)
        return Response({"url": pay_links.link_url(token), "expires_at": link.expires_at,
                         "emailed": bool(payload.validated_data["email"])}, status=201)


class AreaReminderView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Email a payment reminder for my own-area charge",
                   description="One email per charge per local day; 409 when it is not pending or has no account email.",
                   request=None, responses={200: PaymentReconciliationSerializer, **ERRORS})
    def post(self, request, makerspace_id, payment_id):
        from apps.payments.area_reminder import send_reminder

        space = _space(request, makerspace_id)
        if area_queue.in_queue(request.user, space.pk, payment_id) is None:
            raise NotFound()
        payment = send_reminder(actor=request.user, makerspace_id=space.pk, payment_id=payment_id)
        return Response(PaymentReconciliationSerializer(
            with_refunds(Payment.objects.filter(pk=payment.pk)).get(),
            context={"payment_subject_labels": resolve_subject_labels([payment])}).data)
