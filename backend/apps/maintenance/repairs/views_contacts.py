"""The technician directory, opt-in links and per-area defaults (#98, C-4)."""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff

from . import areas, optin, services_contacts as svc
from .serializers_contacts import (
    TechnicianConsentWithdrawSerializer, TechnicianContactSerializer, TechnicianContactWriteSerializer,
    TechnicianDefaultSerializer, TechnicianOptInLinkSerializer,
)
from .views_common import ERRORS, require_any, space_for

TAGS = ["Repairs technicians"]


def _rows():
    from apps.maintenance.models import TechnicianContact, TechnicianCoverage
    return TechnicianContact.objects.select_related("person", "makerspace").prefetch_related(
        Prefetch("coverage", queryset=TechnicianCoverage.objects.select_related("machine_type", "room")))


def _contact(actor, pk):
    row = get_object_or_404(rbac.scope_by_makerspace(actor, _rows()), pk=pk)
    require_any(row.makerspace, areas.REPAIRS)
    if not svc.may_manage_directory(actor, row.makerspace_id):
        raise PermissionDenied()
    return row


def _render(request, row):
    return TechnicianContactSerializer(_rows().get(pk=row.pk), context={"request": request}).data


class TechnicianListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="The technician directory",
                   responses={200: TechnicianContactSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        require_any(space, areas.REPAIRS)
        if not svc.may_manage_directory(request.user, space.pk):
            raise PermissionDenied()
        rows = _rows().filter(makerspace=space)
        if request.query_params.get("archived") != "1":
            rows = rows.filter(is_archived=False)
        return Response(TechnicianContactSerializer(rows[:500], many=True, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Add a technician (in-house person or external contractor)",
                   request=TechnicianContactWriteSerializer, responses={201: TechnicianContactSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        require_any(space, areas.REPAIRS)
        body = TechnicianContactWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = svc.create_contact(request.user, space, dict(body.validated_data))
        return Response(_render(request, row), status=status.HTTP_201_CREATED)


class TechnicianDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="One technician", responses={200: TechnicianContactSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(_render(request, _contact(request.user, pk)))

    @extend_schema(tags=TAGS, summary="Change a technician's details, channels or coverage",
                   request=TechnicianContactWriteSerializer, responses={200: TechnicianContactSerializer, **ERRORS})
    def patch(self, request, pk):
        row = _contact(request.user, pk)
        body = TechnicianContactWriteSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        values = dict(body.validated_data)
        values.pop("person_id", None)  # who an in-house entry names never changes
        return Response(_render(request, svc.update_contact(request.user, row, values)))

    @extend_schema(tags=TAGS, summary="Archive a technician (history is kept)",
                   responses={200: TechnicianContactSerializer, **ERRORS})
    def delete(self, request, pk):
        return Response(_render(request, svc.archive_contact(request.user, _contact(request.user, pk))))


class TechnicianOptInLinkView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Create and email the one-time chat opt-in link",
                   request=None, responses={201: TechnicianOptInLinkSerializer, **ERRORS})
    def post(self, request, pk):
        data = optin.create_link(request.user, _contact(request.user, pk))
        return Response(TechnicianOptInLinkSerializer(data).data, status=status.HTTP_201_CREATED)


class TechnicianConsentView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Withdraw a technician's chat consent (they asked to stop)",
                   request=TechnicianConsentWithdrawSerializer, responses={200: TechnicianContactSerializer, **ERRORS})
    def post(self, request, pk):
        body = TechnicianConsentWithdrawSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = svc.withdraw_consent(request.user, _contact(request.user, pk), body.validated_data["channel"])
        return Response(_render(request, row))


class TechnicianDefaultsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Pre-ticked technicians per area, machine type or room",
                   responses={200: TechnicianDefaultSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from apps.maintenance.models import TechnicianDefault
        space = space_for(request.user, makerspace_id)
        require_any(space, areas.REPAIRS)
        if not svc.may_manage_directory(request.user, space.pk):
            raise PermissionDenied()
        rows = TechnicianDefault.objects.filter(makerspace=space).order_by("area", "id")[:500]
        return Response(TechnicianDefaultSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Add (or with remove=true, drop) one default technician",
                   request=TechnicianDefaultSerializer, responses={200: TechnicianDefaultSerializer(many=True),
                                                                   **ERRORS})
    def post(self, request, makerspace_id):
        from apps.bookings.models import BookableSpace
        from apps.machines.member_scope_services import assignable_machine_types
        from apps.maintenance.models import TechnicianContact
        space = space_for(request.user, makerspace_id)
        require_any(space, areas.REPAIRS)
        body = TechnicianDefaultSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        contact = get_object_or_404(TechnicianContact.objects.filter(makerspace=space), pk=data["contact_id"])
        machine_type = (get_object_or_404(assignable_machine_types(space), pk=data["machine_type_id"])
                        if data.get("machine_type_id") else None)
        room = (get_object_or_404(BookableSpace.objects.filter(makerspace=space), pk=data["room_id"])
                if data.get("room_id") else None)
        svc.set_default(request.user, space, area=data["area"], contact=contact, machine_type=machine_type, room=room,
                        remove=str(request.query_params.get("remove", "")).lower() in ("1", "true"))
        return self.get(request, makerspace_id)


class TechnicianCandidateSerializer(serializers.Serializer):
    person_id = serializers.IntegerField()
    name = serializers.CharField()
    is_technician = serializers.BooleanField()


class TechnicianCandidatesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Staff of this space who can be added as in-house technicians",
                   responses={200: TechnicianCandidateSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        from apps.maintenance.models import TechnicianContact
        from apps.makerspaces.models import MakerspaceMembership
        space = space_for(request.user, makerspace_id)
        require_any(space, areas.REPAIRS)
        if not svc.may_manage_directory(request.user, space.pk):
            raise PermissionDenied()
        taken = TechnicianContact.objects.filter(makerspace=space, person__isnull=False).values("person_id")
        rows = (MakerspaceMembership.staff_tracks.filter(makerspace=space, status="active").exclude(user_id__in=taken)
                .select_related("user").order_by("user__username")[:500])
        from apps.accounts.pii_presentation import MASK, pii_visible
        visible = pii_visible(request.user, space.pk)
        return Response([{"person_id": row.user_id, "name": (row.user.display_name or row.user.username) if visible else MASK,
                          "is_technician": rbac.can(row.user, rbac.Action.WORK_REPAIRS, space.pk)} for row in rows])
