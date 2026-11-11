"""Consistent no-store, command header and paginated API boundaries."""
from uuid import UUID
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from .admission_errors import fail
from .admission_feature import hackathon_enabled
from .admission_transactions import member_event, require_programme


def require_hackathon(event):
    if not hackathon_enabled(event.makerspace):
        fail("not_found", "Not found.", status=404)


class ProgrammeCommandThrottle(SimpleRateThrottle):
    scope = "event_programme_command"
    rate = "30/min"

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ProgrammeView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if not isinstance(response.data, dict) or "code" not in response.data:
            from rest_framework.exceptions import ValidationError
            fields = response.data if isinstance(exc, ValidationError) and isinstance(response.data, dict) else {}
            codes = {400: "invalid_input", 401: "authentication_required", 403: "permission_denied",
                     404: "not_found", 405: "method_not_allowed", 429: "throttled"}
            detail = response.data.get("detail") if isinstance(response.data, dict) else None
            response.data = {"code": codes.get(response.status_code, "request_failed"),
                             "detail": str(detail or "Review the submitted fields."), "fields": fields}
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Cookie, Authorization"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def member_target(self, request, makerspace_id, pk):
        return member_event(request.user, pk, makerspace_id)

    def team_target(self, request, makerspace_id, pk):
        """Teams, the finder and submissions belong to hackathons alone: off = 404 everywhere (decision 218)."""
        event, config = self.member_target(request, makerspace_id, pk)
        require_hackathon(event)
        return event, config

    def command_data(self, request, serializer_class, **context):
        serializer = serializer_class(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            header = UUID(request.headers.get("Idempotency-Key", ""))
        except (ValueError, TypeError, AttributeError):
            fail("idempotency_key_required", "Provide the operation UUID as Idempotency-Key.", status=400)
        if header != data["operation_id"]:
            fail("idempotency_key_mismatch", "The operation ID and header must match.", status=400)
        return data


class MemberCommandView(ProgrammeView):
    throttle_classes = [ProgrammeCommandThrottle]


class AdminView(ProgrammeView):
    permission_classes = [IsActiveStaff]
    permission = "review_applications"

    def admin_target(self, request, pk):
        event = event_authority.get_event(request.user, pk, self.permission)
        return event, require_programme(event)

    def team_admin_target(self, request, pk):
        event, config = self.admin_target(request, pk)
        require_hackathon(event)
        return event, config


class ProgrammePagination(PageNumberPagination):
    page_size = 24


def paginated(request, rows, projection):
    pagination = ProgrammePagination()
    page = pagination.paginate_queryset(rows, request)
    return pagination.get_paginated_response([projection(row) for row in page])
