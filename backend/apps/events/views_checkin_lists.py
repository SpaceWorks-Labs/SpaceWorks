"""Custom check-in list routes (lane L21a, X45). Online only; scans never touch entry check-in."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response

from apps.admin_api.permissions import IsActiveStaff

from . import checkin_lists, event_authority
from .hackathons.api_base import ProgrammeCommandThrottle, ProgrammeView
from .hackathons.api_schema import ERRORS
from .models import EventRegistration
from .models_checkin_lists import EventCheckInList
from .serializers_participation import (
    CheckInListEligibilitySerializer, CheckInListInput, CheckInListReorderInput, CheckInListScanInput,
    CheckInListSerializer,
)

TAGS = ["Event check-in lists"]


def masked(request, event, row):
    """A superadmin without an open PII window for this space sees the name masked (#114.1)."""
    from apps.accounts.pii_presentation import mask_data, pii_visible
    if not pii_visible(request.user, event.makerspace_id):
        mask_data(row, ("name",))
    return row


class ListView(ProgrammeView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ProgrammeCommandThrottle]

    def target(self, request, pk, permission):
        event = event_authority.get_event(request.user, pk, permission)
        checkin_lists.require_feature(event)
        return event

    def payload(self, request):
        data = CheckInListInput(data=request.data)
        data.is_valid(raise_exception=True)
        return data.validated_data


class CheckInListsView(ListView):
    @extend_schema(tags=TAGS, request=None, responses={200: CheckInListSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        event = self.target(request, pk, "check_in")
        rows = EventCheckInList.objects.filter(event=event).select_related("addon").order_by("archived_at", "pk")
        return Response([checkin_lists.project(row) for row in rows])

    @extend_schema(tags=TAGS, request=CheckInListInput, responses={201: CheckInListSerializer, **ERRORS})
    def post(self, request, pk):
        event = self.target(request, pk, "manage_registrations")
        return Response(checkin_lists.project(checkin_lists.create(event, actor=request.user,
                                                                   data=self.payload(request))), status=201)


class CheckInListDetailView(ListView):
    @extend_schema(tags=TAGS, request=CheckInListInput, responses={200: CheckInListSerializer, **ERRORS},
                   summary="Rename or change a list, or archive it (archived lists are read-only)")
    def patch(self, request, pk, list_id):
        event = self.target(request, pk, "manage_registrations")
        return Response(checkin_lists.project(checkin_lists.update(event, actor=request.user, list_id=list_id,
                                                                   data=self.payload(request))))


class CheckInListLookupView(ListView):
    @extend_schema(tags=TAGS, request=None, responses={200: CheckInListEligibilitySerializer, **ERRORS},
                   parameters=[OpenApiParameter("registration_id", int, required=True)],
                   summary="May this person collect from the list, and how many times so far")
    def get(self, request, pk, list_id):
        event = self.target(request, pk, "check_in")
        row = get_object_or_404(EventCheckInList, pk=list_id, event=event)
        try:
            registration_id = int(request.query_params.get("registration_id", ""))
        except ValueError:
            registration_id = 0
        registration = get_object_or_404(EventRegistration, pk=registration_id, event=event)
        allowed, used, reason = checkin_lists.eligibility(row, registration)
        return Response(masked(request, event, {"registration_id": registration.pk, "name": registration.name,
                                                "allowed": allowed, "used": used, "reason": reason}))


class CheckInListScanView(ListView):
    @extend_schema(tags=TAGS, request=CheckInListScanInput, responses={201: CheckInListEligibilitySerializer, **ERRORS},
                   summary="Record one collection on the list (idempotent by operation id)")
    def post(self, request, pk, list_id):
        event = self.target(request, pk, "check_in")
        data = CheckInListScanInput(data=request.data)
        data.is_valid(raise_exception=True)
        scan, (allowed, used, reason) = checkin_lists.scan(event, actor=request.user, list_id=list_id,
                                                          **data.validated_data)
        return Response(masked(request, event, {"scan_id": scan.pk, "registration_id": scan.registration_id,
                                                "undo_until": scan.scanned_at + checkin_lists.UNDO_WINDOW,
                                                "name": scan.registration.name, "allowed": allowed, "used": used,
                                                "reason": reason}), status=201)


class CheckInListReorderView(ListView):
    @extend_schema(tags=TAGS, request=CheckInListReorderInput, responses={200: CheckInListSerializer(many=True), **ERRORS},
                   summary="Set the desk order of the open lists (name each open list once)")
    def post(self, request, pk):
        event = self.target(request, pk, "manage_registrations")
        data = CheckInListReorderInput(data=request.data)
        data.is_valid(raise_exception=True)
        rows = checkin_lists.reorder(event, actor=request.user, ordered_ids=data.validated_data["ordered_ids"])
        return Response([checkin_lists.project(row) for row in rows])


class CheckInListScanUndoView(ListView):
    @extend_schema(tags=TAGS, request=None, responses={200: CheckInListEligibilitySerializer, **ERRORS},
                   summary="Undo a collection within 60 seconds (the record stays, marked undone)")
    def post(self, request, pk, list_id, scan_id):
        event = self.target(request, pk, "check_in")
        scan = checkin_lists.undo(event, actor=request.user, list_id=list_id, scan_id=scan_id)
        allowed = checkin_lists.allowance(scan.checkin_list, scan.registration)
        return Response(masked(request, event, {"scan_id": scan.pk, "registration_id": scan.registration_id,
                                                "name": scan.registration.name, "allowed": allowed,
                                                "used": checkin_lists.used(scan.checkin_list, scan.registration),
                                                "reason": None}))
