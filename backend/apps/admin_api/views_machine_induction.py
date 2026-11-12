"""Induction events: mark an event as an induction, then grant from its attendees (decision 223 (k)).

Authority: MANAGE_MACHINES narrowed to the certification's machine type (the same check as
every other certification grant); linking also needs authority on the event (decision 224 b). Every route answers 404 while `machines.induction_events`
(or the events or machines module) is off. Nothing is granted without the staff POST.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.machines.retired import RetiredCertificationView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.models import Event
from apps.machines import access, induction
from apps.machines.models import CertificationType, EventInductionLink, GuestCertificationGrant
from apps.machines.serializers_workshop import (
    GuestGrantRevokeSerializer, InductionGrantResponseSerializer, InductionGrantSerializer,
    InductionLinkCreateSerializer, InductionLinkSerializer, InductionOverviewSerializer, _name,
)
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.openapi_errors import errors

TAGS = ["Admin machine induction"]


def _space_event(actor, makerspace_id, event_id):
    space = get_object_or_404(rbac.scope_by_visibility_or_action(
        actor, rbac.Action.MANAGE_MACHINES, Makerspace.objects.all(), field="id"), pk=makerspace_id)
    induction.require_induction(space)
    if not rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk):
        raise PermissionDenied()
    return space, get_object_or_404(Event.objects.filter(makerspace=space), pk=event_id)


def _overview(actor, event):
    links = [row for row in EventInductionLink.objects.filter(event=event).select_related(
        "certification_type__machine_type") if induction._may_grant(actor, row.certification_type)]
    member_ids = set(MakerspaceMembership.objects.filter(
        makerspace=event.makerspace, status="active").values_list("user_id", flat=True))
    attendees = []
    # The attendee list is the event's data: it is shown only through an induction link for a
    # certification the reader may grant, never for an arbitrary event of the space.
    for registration in induction.attendees(event) if links else ():
        user = registration.member
        held = [row.certification_type_id for row in links if induction.holds_type(user, row.certification_type)]
        attendees.append({"user_id": user.pk, "name": _name(user), "is_member": user.pk in member_ids,
                          "certified_type_ids": held})
    return {"links": links, "attendees": attendees, "can_grant": bool(links)}


class EventInductionView(RetiredCertificationView, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Induction links and checked-in attendees for an event", request=None,
                   responses={200: InductionOverviewSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id, event_id):
        _space, event = _space_event(request.user, makerspace_id, event_id)
        payload = _overview(request.user, event)
        payload["links"] = InductionLinkSerializer(payload["links"], many=True).data
        return Response(payload)

    @extend_schema(tags=TAGS, summary="Mark an event as an induction for a certification",
                   request=InductionLinkCreateSerializer,
                   responses={201: InductionLinkSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id, event_id):
        space, event = _space_event(request.user, makerspace_id, event_id)
        # Decision 224(b): marking an event as an induction also needs authority over that event
        # (Event Manager, its organizer or a co-organizer), so machine staff cannot adopt an event
        # they do not run and read its attendees.
        if not event_authority.can_manage_grants(request.user, event):
            raise PermissionDenied()
        serializer = InductionLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = get_object_or_404(CertificationType.objects.filter(makerspace=space),
                                pk=serializer.validated_data["certification_type_id"])
        link = induction.link(event, row, actor=request.user)
        return Response(InductionLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class EventInductionUnlinkView(RetiredCertificationView, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Remove an induction link (grants already made stay)", request=None,
                   responses={204: None, **errors(401, 403, 404)})
    def delete(self, request, pk):
        link = get_object_or_404(rbac.scope_by_makerspace(request.user, EventInductionLink.objects.all()).select_related(
            "certification_type__machine_type", "makerspace"), pk=pk)
        induction.unlink(link, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventInductionGrantView(RetiredCertificationView, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Grant the event's certifications to chosen attendees",
                   request=InductionGrantSerializer,
                   responses={200: InductionGrantResponseSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id, event_id):
        _space, event = _space_event(request.user, makerspace_id, event_id)
        serializer = InductionGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        results = induction.grant_from_induction(
            event, data["user_ids"], actor=request.user, certification_type_ids=data.get("certification_type_ids"),
            expires_at=data.get("expires_at"))
        return Response({"results": results})


class GuestCertificationRevokeView(RetiredCertificationView, APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Revoke a guest certification", request=GuestGrantRevokeSerializer,
                   responses={204: None, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        serializer = GuestGrantRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = get_object_or_404(rbac.scope_by_makerspace(request.user, GuestCertificationGrant.objects.all()), pk=pk)
        if not access.can_create_machine(request.user, grant.makerspace_id, grant.certification_type.machine_type):
            raise PermissionDenied()
        induction.revoke_guest_grant(grant, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
