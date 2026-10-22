"""Shared authorization and response helpers for staff machine-service views."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts import rbac
from apps.admin_api.serializers_machine_service import MachineServiceRequestSerializer
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines.service_request_partitions import (
    collect_partition_q,
    machine_partition_q,
)
from apps.machines.models import MachineServiceRequest
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace


SERVICE_ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid service request input."),
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(description="Machine management permission required."),
    404: OpenApiResponse(description="Service request was not found."),
    409: OpenApiResponse(ErrorSerializer, description="Service workflow conflict."),
}
SERVICE_FILTERS = [
    OpenApiParameter("status", str, OpenApiParameter.QUERY),
    OpenApiParameter("machine", int, OpenApiParameter.QUERY),
    OpenApiParameter("bucket", int, OpenApiParameter.QUERY),
    OpenApiParameter("queue", int, OpenApiParameter.QUERY),
    OpenApiParameter("machine_type", str, OpenApiParameter.QUERY),
    OpenApiParameter("machine_type_id", int, OpenApiParameter.QUERY),
]


def _base_queryset():
    return MachineServiceRequest.objects.select_related(
        "makerspace",
        "bucket__machine__machine_type",
        "queue__machine_type",
        "assigned_machine__machine_type",
        "requester",
    ).prefetch_related("files", "consumptions")


def _visible_makerspace(actor, makerspace_id, action=rbac.Action.MANAGE_MACHINES):
    makerspace = get_object_or_404(
        rbac.scope_by_visibility_or_action(
            actor, action, Makerspace.objects.all(), field="id"
        ),
        pk=makerspace_id,
    )
    require_module(makerspace, "machine_service")
    if not rbac.can(actor, action, makerspace.pk):
        raise PermissionDenied()
    return makerspace


def _manage_queryset(actor, makerspace_id):
    """Machine-scoped rows only, for lifecycle mutations and service files.

    ``makerspace_id`` is required: the partition is resolved per makerspace, and both
    callers reach this through ``_resolve_request``, which has already established which
    tenant the row belongs to.
    """
    queryset = rbac.scope_by_action(
        actor,
        rbac.Action.MANAGE_MACHINES,
        _base_queryset(),
        field="makerspace_id",
    ).filter(makerspace_id=makerspace_id)
    partition = machine_partition_q(actor, makerspace_id)
    if partition is not None:
        queryset = queryset.filter(partition)
    return queryset.distinct()


def _read_or_collect_queryset(actor, makerspace_id):
    """Machine partition plus the cumulative direct-collect completed partition."""
    queryset = rbac.scope_by_action(
        actor,
        rbac.Action.COLLECT_SERVICE_REQUEST,
        _base_queryset(),
        field="makerspace_id",
    ).filter(makerspace_id=makerspace_id)
    visible = collect_partition_q(actor, makerspace_id)
    if visible is None:
        return queryset.distinct()
    return queryset.filter(visible).distinct()


def _resolve_request(actor, pk, *, action, queryset_builder):
    # Establish tenant visibility first: foreign/hidden rows stay a 404 while an actor
    # who can see the makerspace but lacks the requested action receives a 403.
    row = get_object_or_404(
        rbac.scope_by_visibility_or_action(
            actor,
            action,
            _base_queryset(),
            field="makerspace_id",
        ),
        pk=pk,
    )
    require_module(row.makerspace, "machine_service")
    if not rbac.can(actor, action, row.makerspace_id):
        raise PermissionDenied()
    return get_object_or_404(queryset_builder(actor, row.makerspace_id), pk=row.pk)


def _manageable_request(actor, pk):
    return _resolve_request(
        actor,
        pk,
        action=rbac.Action.MANAGE_MACHINES,
        queryset_builder=_manage_queryset,
    )


def _readable_or_collectable_request(actor, pk):
    return _resolve_request(
        actor,
        pk,
        action=rbac.Action.COLLECT_SERVICE_REQUEST,
        queryset_builder=_read_or_collect_queryset,
    )


def _query_int(request, name):
    value = request.query_params.get(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Must be an integer."}) from exc


def _response(row, code=status.HTTP_200_OK):
    from apps.machines.service_queue_eta import queue_snapshot_for
    row = _base_queryset().get(pk=row.pk)
    # Rebuilt after any mutation: an action response never reuses a pre-mutation snapshot.
    context = {"queue_snapshot": queue_snapshot_for([row])}
    return Response(MachineServiceRequestSerializer(row, context=context).data, status=code)
