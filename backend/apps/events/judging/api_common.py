"""No-store APIs, exact origin/member target checks and schema helpers."""

from django.utils.translation import gettext
from collections.abc import Mapping
from uuid import UUID

from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.events import event_authority
from apps.events.models import Event
from apps.hardware_requests.exceptions import ErrorSerializer
from .boundary import active_member
from .ports import runtime
from .errors import ProgrammeError

ERRORS = {status: ErrorSerializer for status in (400, 401, 403, 404, 409, 410, 413, 423, 429, 503)}
PAGE = [OpenApiParameter("page", int, OpenApiParameter.QUERY)]


def schema(*, request=None, response=None, status=200, page=False, public=False, description=""):
    if page and isinstance(response, serializers.ListSerializer):
        child = response.child
        response = inline_serializer(name=f"{type(child).__name__}Page", fields={
            "count": serializers.IntegerField(), "next": serializers.URLField(allow_null=True),
            "previous": serializers.URLField(allow_null=True), "results": type(child)(many=True),
        })
    parameters = list(PAGE) if page else []
    if request is not None:
        parameters.append(OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True,
                                           description="The command operation_id UUID; replay requires identical body and route."))
    return extend_schema(tags=["Event programme judging"], request=request,
        responses={status: response, **ERRORS}, parameters=parameters,
        **({"auth": []} if public else {}), description=description)


def paginated(request, rows, serializer=None, **extra):
    paginator = PageNumberPagination()
    paginator.page_size = 24
    page = paginator.paginate_queryset(rows, request)
    result = serializer(page, many=True).data if serializer else page
    response = paginator.get_paginated_response(result)
    response.data.update(extra)
    return response


class PrivateView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            self.validate_command_header(request)

    @staticmethod
    def validate_command_header(request):
        try:
            if not isinstance(request.data, Mapping):
                raise ValueError
            operation = UUID(str(request.data.get("operation_id")))
            header = UUID(str(request.headers.get("Idempotency-Key")))
            if operation != header:
                raise ValueError
        except (ValueError, TypeError, AttributeError) as exc:
            raise ProgrammeError("invalid_idempotency_key", gettext("Idempotency-Key must match the command operation_id."), status=400) from exc

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class MemberView(PrivateView):
    permission_classes = [IsAuthenticated]

    def event(self, request, pk, makerspace_id):
        active_member(request.user)
        event = Event.objects.select_related("makerspace").filter(pk=pk, makerspace_id=makerspace_id).first()
        if event is None:
            raise Http404
        runtime().require_programme(event)
        return event


def admin_event(request, pk, permission="manage_hackathon"):
    event = event_authority.get_event(request.user, pk, permission)
    runtime().require_programme(event)
    return event


def admin_event_for(actor, pk, permission="manage_hackathon"):
    """`admin_event` for a service that holds the actor, not the request."""
    event = event_authority.get_event(actor, pk, permission)
    runtime().require_programme(event)
    return event
