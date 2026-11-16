"""Staff machine access (decision 319): who may use which machine, granted by the Space Manager.

`GET/POST makerspaces/<id>/machine-access` lists and grants (one or many members, one machine or one machine
type, optional expiry and note); `POST machine-access/<pk>/revoke` revokes; `PATCH machines/<pk>/open-access`
turns "open to all members" on or off. Authority is the machine authority itself (`access_grants_services`):
the Space Manager always, a Machine Manager inside their machine scope. A row outside the caller's space or
scope is a 404 / absent, never a 403 that confirms it exists.
"""
from django.utils.translation import gettext
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.machine_access import resolve_machine
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.machines import access
from apps.machines.access_grants_services import bulk_grant, can_grant, manageable_grants, revoke_access
from apps.machines.models import Machine, MachineAccessGrant, MachineType
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.openapi_errors import errors


NOT_A_MEMBER = "An active member of this makerspace is required."


def _name(user):
    return (user.display_name or user.get_full_name() or user.username) if user else ""


def grant_status(row, now=None):
    if row.revoked_at is not None:
        return "revoked"
    return "live" if row.is_live(now) else "expired"


class MachineAccessGrantSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    machine_name = serializers.CharField(source="machine.name", default=None, read_only=True)
    machine_type_name = serializers.CharField(source="machine_type.name", default=None, read_only=True)
    granted_by_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = MachineAccessGrant
        fields = ["id", "member", "member_name", "machine", "machine_name", "machine_type", "machine_type_name",
                  "granted_by_name", "granted_at", "expires_at", "note", "source", "revoked_at", "status"]

    def get_member_name(self, obj) -> str:
        return _name(obj.member)

    def get_granted_by_name(self, obj) -> str:
        return _name(obj.granted_by)

    def get_status(self, obj) -> str:
        return grant_status(obj)


class MachineAccessGrantPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = MachineAccessGrantSerializer(many=True)


class MachineAccessCreateSerializer(serializers.Serializer):
    member_ids = serializers.ListField(child=serializers.IntegerField(), max_length=200, required=False, default=list)
    # The member register selects memberships, not accounts: either id list works (same space only).
    membership_ids = serializers.ListField(child=serializers.IntegerField(), max_length=200, required=False, default=list)
    machine_id = serializers.IntegerField(required=False, allow_null=True)
    machine_type_id = serializers.IntegerField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")

    def validate(self, attrs):
        if not attrs["member_ids"] and not attrs["membership_ids"]:
            raise serializers.ValidationError({"member_ids": gettext("Choose at least one member.")})
        return attrs


class MachineAccessCreateResultSerializer(serializers.Serializer):
    granted = MachineAccessGrantSerializer(many=True)
    failed = serializers.ListField(child=serializers.DictField())


class OpenAccessSerializer(serializers.Serializer):
    open_to_all_members = serializers.BooleanField()


def _space(user, makerspace_id):
    space = get_object_or_404(rbac.scope_by_makerspace(user, Makerspace.objects.all(), makerspace_field="id"),
                              pk=makerspace_id)
    require_module(space, "machines")
    if not rbac.can(user, rbac.Action.MANAGE_MACHINES, space.pk):
        raise PermissionDenied()
    return space


def _allowed(user, rows):
    """Rows the caller may manage, so a Machine Manager sees only their scope (shared with the report)."""
    return manageable_grants(user, rows)


class MachineAccessView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machines"], summary="List machine access grants",
                   parameters=[OpenApiParameter("page", int, OpenApiParameter.QUERY),
                               OpenApiParameter("machine_id", int, OpenApiParameter.QUERY),
                               OpenApiParameter("machine_type_id", int, OpenApiParameter.QUERY),
                               OpenApiParameter("member_id", int, OpenApiParameter.QUERY),
                               OpenApiParameter("source", str, OpenApiParameter.QUERY,
                                                enum=list(MachineAccessGrant.Source.values)),
                               OpenApiParameter("status", str, OpenApiParameter.QUERY,
                                                enum=["live", "expired", "revoked", "all"])],
                   responses={200: MachineAccessGrantPageSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        rows = MachineAccessGrant.objects.filter(makerspace=space).select_related(
            "member", "machine", "machine_type", "granted_by", "makerspace")
        for key in ("machine_id", "machine_type_id", "member_id"):
            value = request.query_params.get(key)
            if value:
                if not value.isdigit():
                    raise serializers.ValidationError({key: gettext("Must be a number.")})
                rows = rows.filter(**{key: int(value)})
        source = request.query_params.get("source")
        if source:
            # `source=migration` is the "review converted grants" list (decision 335(a)).
            if source not in MachineAccessGrant.Source.values:
                raise serializers.ValidationError({"source": gettext("Unknown grant source.")})
            rows = rows.filter(source=source)
        now, wanted = timezone.now(), request.query_params.get("status", "live")
        rows = [row for row in _allowed(request.user, rows) if wanted == "all" or grant_status(row, now) == wanted]
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(MachineAccessGrantSerializer(page, many=True).data)

    @extend_schema(tags=["Admin machines"], summary="Grant machine access to one or many members",
                   request=MachineAccessCreateSerializer,
                   responses={201: MachineAccessCreateResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        data = MachineAccessCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        machine = get_object_or_404(Machine, pk=v["machine_id"], makerspace=space) if v.get("machine_id") else None
        machine_type = None
        if v.get("machine_type_id"):
            # `makerspace__in=[space, None]` silently drops None, so built-in types were a 404 (M8).
            machine_type = get_object_or_404(MachineType.objects.filter(
                Q(makerspace=space) | Q(makerspace__isnull=True)), pk=v["machine_type_id"])
        if not can_grant(request.user, space, machine=machine, machine_type=machine_type):
            raise PermissionDenied()
        wanted = set(v["member_ids"]) | set(MakerspaceMembership.objects.filter(
            makerspace=space, pk__in=v["membership_ids"]).values_list("user_id", flat=True))
        # Only this space's active members are ever looked up (L-M4): an account that exists elsewhere
        # and an id that exists nowhere get the same answer, so the route is no global user-id oracle.
        members = list(User.objects.filter(is_active=True, pk__in=MakerspaceMembership.objects.filter(
            makerspace=space, status="active", user_id__in=wanted).values("user_id")))
        found = {m.pk for m in members}
        done, failed = bulk_grant(request.user, space, members, machine=machine, machine_type=machine_type,
                                  expires_at=v.get("expires_at"), note=v.get("note", ""))
        failed += [{"member_id": pk, "detail": gettext(NOT_A_MEMBER)} for pk in sorted(wanted) if pk not in found]
        return Response({"granted": MachineAccessGrantSerializer(done, many=True).data, "failed": failed}, status=201)


class MachineAccessRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machines"], summary="Revoke a machine access grant", request=None,
                   responses={200: MachineAccessGrantSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        row = get_object_or_404(rbac.scope_by_makerspace(request.user, MachineAccessGrant.objects.select_related(
            "machine", "machine_type", "makerspace", "member"), makerspace_field="makerspace_id"), pk=pk)
        require_module(row.makerspace, "machines")
        # A grant outside the caller's machine scope is as absent as one in another space (L-M4).
        if not can_grant(request.user, row.makerspace, machine=row.machine, machine_type=row.machine_type):
            raise Http404
        return Response(MachineAccessGrantSerializer(revoke_access(request.user, row)).data)


class MachineOpenAccessView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machines"], summary="Open a machine to all members, or close it",
                   request=OpenAccessSerializer, responses={200: OpenAccessSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        machine = resolve_machine(request.user, pk)
        require_module(machine.makerspace_id, "machines")
        if not access.is_machine_admin(request.user, machine):
            raise PermissionDenied()
        data = OpenAccessSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        value = data.validated_data["open_to_all_members"]
        with transaction.atomic():
            locked = Machine.objects.select_for_update().get(pk=machine.pk)
            if locked.open_to_all_members != value:
                previous, locked.open_to_all_members = locked.open_to_all_members, value
                locked.save(update_fields=["open_to_all_members", "updated_at"])
                audit.record(request.user, "machine.open_access_changed", makerspace=locked.makerspace, target=locked,
                             meta={"from": previous, "to": value})
        return Response({"open_to_all_members": locked.open_to_all_members})
