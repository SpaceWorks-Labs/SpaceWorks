from django.shortcuts import get_object_or_404
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.models import Event
from apps.makerspaces.guards import require_feature, require_module
from .commands import active_member
from .errors import ProgrammeError


class ProgrammeThrottle(UserRateThrottle):
    scope = "events_programme"
    rate = "90/min"


class ProgrammeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProgrammeThrottle]
    admin = False
    permission = "mentor_queue"
    feature = "events.mentoring"

    def event(self, request, pk, makerspace_id=None):
        if self.admin:
            event = event_authority.get_event(request.user, pk, self.permission)
        else:
            active_member(request.user)
            event = get_object_or_404(Event.objects.select_related("makerspace"), pk=pk)
            if makerspace_id is not None and event.makerspace_id != makerspace_id:
                # Collaborative-origin resolution is G's adapter, never a client hint.
                raise ProgrammeError("not_found", "Not found.", status=404)
            require_module(event.makerspace, "events")
        if self.feature:
            require_feature(event.makerspace, self.feature)
            from .ports import ports
            ports().require_event_feature(event_id=event.pk, feature=self.feature)
        return event

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def input(self, request, serializer):
        parsed = serializer(data=request.data)
        if not parsed.is_valid():
            raise ProgrammeError("invalid_input", "Check the highlighted fields.", status=400, fields=parsed.errors)
        data = parsed.validated_data
        if str(request.headers.get("Idempotency-Key", "")) != str(data["operation_id"]):
            raise ProgrammeError("idempotency_key_required", "Idempotency-Key must equal operation_id.", status=400)
        return data


class AdminView(ProgrammeView):
    admin = True
    permission_classes = [IsActiveStaff]


def paginated(request, rows, project):
    pager = PageNumberPagination()
    pager.page_size = 24
    page = pager.paginate_queryset(rows, request)
    return pager.get_paginated_response([project(row) for row in page])


def page_schema(name, item):
    return inline_serializer(name=name, fields={"count": serializers.IntegerField(),
        "next": serializers.URLField(allow_null=True), "previous": serializers.URLField(allow_null=True),
        "results": item(many=True)})


def envelope(row, allowed=()):
    data = {"id": row.pk, "event_id": row.event_id, "version": row.version, "allowed_actions": list(allowed)}
    if hasattr(row, "state"):
        data["state"] = row.state
    return data
