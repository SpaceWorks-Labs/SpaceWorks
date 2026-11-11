"""Decision 242 / U5: bulk approve, reject and refund-decision endpoints for the high-volume queues.

Each handler runs the SAME single-row service as the single-item route, with the SAME per-row authority lookup
(`rbac.scope_by_action`, the booking and event authority, the refund-case reach), inside ONE transaction: the
batch is all-or-nothing, so a refusal on any row rolls every earlier row back and names the failing id. The
services emit their own audit entry per row, so the trail is one row per decision, never one blob. At most 50
ids per call; ids must be unique.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

MAX_IDS = 50
ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404, 409)}


class BulkFailed(APIException):
    status_code = 409
    default_code = "bulk_failed"

    def __init__(self, failed_id, cause):
        detail = getattr(cause, "detail", None)
        self.detail = {"detail": "Nothing was changed: one item could not be decided.", "code": "bulk_failed",
                       "failed_id": failed_id, "cause": detail if isinstance(detail, (dict, list, str)) else str(cause)}


class BulkIds(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=MAX_IDS)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")

    def validate_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Ids must be unique.")
        return value


class BulkResultSerializer(serializers.Serializer):
    decided = serializers.IntegerField()
    ids = serializers.ListField(child=serializers.IntegerField())


class _BulkView(APIView):
    permission_classes = [IsActiveStaff]
    decisions = ()
    needs_reason = ()

    def decide(self, actor, pk, decision, reason):  # pragma: no cover - overridden
        raise NotImplementedError

    def post(self, request, decision):
        payload = BulkIds(data=request.data)
        payload.is_valid(raise_exception=True)
        ids, reason = payload.validated_data["ids"], payload.validated_data["reason"]
        if decision in self.needs_reason and not reason.strip():
            raise serializers.ValidationError({"reason": "A reason is required for this decision."})
        with transaction.atomic():
            for pk in ids:
                try:
                    with transaction.atomic():
                        self.decide(request.user, pk, decision, reason)
                except APIException as exc:
                    raise BulkFailed(pk, exc) from exc
        return Response({"decided": len(ids), "ids": ids})


class RequestBulkDecideView(_BulkView):
    needs_reason = ("reject",)

    @extend_schema(tags=["Admin requests"], summary="Accept or reject many borrow requests (all or nothing)",
                   description="`decision` in the path: accept | reject (reject needs `reason`). Per-row authority as "
                               "the single routes; one audit row each; up to 50 ids.",
                   request=BulkIds, responses={200: BulkResultSerializer, **ERRORS})
    def post(self, request, decision):
        if decision not in ("accept", "reject"):
            raise serializers.ValidationError({"decision": "Use accept or reject."})
        return super().post(request, decision)

    def decide(self, actor, pk, decision, reason):
        from apps.accounts import rbac
        from apps.hardware_requests import workflow
        from apps.hardware_requests.review_views import _scoped_request

        if decision == "accept":
            workflow.accept_request(actor, _scoped_request(actor, pk, rbac.Action.ACCEPT_REQUEST), accepted=None)
        else:
            workflow.reject_request(actor, _scoped_request(actor, pk, rbac.Action.REJECT_REQUEST), reason)


class BookingBulkDecideView(_BulkView):
    needs_reason = ("reject",)

    @extend_schema(tags=["Admin bookings"], summary="Approve or reject many bookings (all or nothing)",
                   description="`decision` in the path: approve | reject (reject needs `reason`).",
                   request=BulkIds, responses={200: BulkResultSerializer, **ERRORS})
    def post(self, request, decision):
        if decision not in ("approve", "reject"):
            raise serializers.ValidationError({"decision": "Use approve or reject."})
        return super().post(request, decision)

    def decide(self, actor, pk, decision, reason):
        from apps.bookings import services
        from apps.bookings.views_admin_booking_actions import _manageable_booking

        booking = _manageable_booking(actor, pk)
        if decision == "approve":
            services.approve_booking(booking, actor=actor)
        else:
            services.reject_booking(booking, actor=actor, reason=reason)


class RegistrationBulkDecideView(_BulkView):
    @extend_schema(tags=["Admin events"], summary="Approve or reject many event registrations (all or nothing)",
                   description="`decision` in the path: approve | reject. Authority is each event's manage_registrations.",
                   request=BulkIds, responses={200: BulkResultSerializer, **ERRORS})
    def post(self, request, decision):
        if decision not in ("approve", "reject"):
            raise serializers.ValidationError({"decision": "Use approve or reject."})
        return super().post(request, decision)

    def decide(self, actor, pk, decision, reason):
        from apps.events import services_registration_state as state
        from apps.events.event_permissions import MANAGE_REGISTRATIONS
        from apps.events.views_admin_event_detail import _manageable_registration

        registration = _manageable_registration(actor, pk, MANAGE_REGISTRATIONS)
        (state.approve_registration if decision == "approve" else state.reject_registration)(registration, actor=actor)


class RefundCaseBulkDecideView(_BulkView):
    needs_reason = ("decline",)

    @extend_schema(tags=["Payments"], summary="Approve or decline many refund cases (all or nothing)",
                   description=("`decision` in the path: approve | decline (decline needs `reason`, the note shown to "
                                "the member). Approve takes each case's due amount; an offline-paid case needs its own "
                                "receipt, so it fails the batch and is decided singly."),
                   request=BulkIds, responses={200: BulkResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, decision):
        if decision not in ("approve", "decline"):
            raise serializers.ValidationError({"decision": "Use approve or decline."})
        self.makerspace_id = makerspace_id
        return super().post(request, decision)

    def decide(self, actor, pk, decision, reason):
        from apps.payments.refund_case_access import get_visible_case, require_queue
        from apps.payments.services_refund_decisions import approve_case, decline_case

        require_queue(actor, self.makerspace_id)
        case = get_visible_case(actor, self.makerspace_id, pk)
        if decision == "approve":
            approve_case(case, actor=actor)
        else:
            decline_case(case, actor=actor, note=reason)
