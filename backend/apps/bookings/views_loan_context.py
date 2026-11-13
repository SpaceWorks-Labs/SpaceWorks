"""Staff booking-context endpoint over a scoped existing hardware request."""
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import serializers
from apps.admin_api.permissions import IsActiveStaff
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.hardware_requests.loan_context_access import request_for_path, safe_id
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from apps.hardware_requests.openapi_loan_context import LoanContextSchema
from .loan_context_services import mutate, read
from .serializers_loan_context import BookingContextPut, ContextCAS, SafeInteger
from django.utils.translation import gettext


class BookingContextResponse(serializers.Serializer):
    active = serializers.BooleanField()
    generation = serializers.UUIDField()
    revision = SafeInteger()
    can_write = serializers.BooleanField()
    booking_id = SafeInteger(minimum=1, required=False)


def _intended(request):
    raw = request.query_params.get("intended_booking_id")
    if raw is None:
        return None
    if not raw.isascii() or not raw.isdecimal() or raw.startswith("0") or len(raw) > 16:
        from rest_framework.exceptions import NotFound
        raise NotFound()
    return safe_id(int(raw))


class BookingLoanContextView(APIView):
    permission_classes = [IsActiveStaff]
    schema = LoanContextSchema()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Decision 216 item 18: the linked write is session-only; reads stay token-readable.
        if request.method in ("PUT", "DELETE") and (
                getattr(request, "api_client", None) or getattr(request, "person_credential", None)):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(gettext("This endpoint requires a staff session."))

    def _request(self, **kwargs):
        return request_for_path(kwargs["makerspace_id"], kwargs.get("request_id"), kwargs.get("loan_id"))

    @extend_schema(parameters=[OpenApiParameter("intended_booking_id", int, required=False)], responses={**PUBLIC_ERROR_RESPONSES, 200: BookingContextResponse})
    def get(self, request, **kwargs):
        return Response(read(request.user, self._request(**kwargs), _intended(request)))

    @extend_schema(request=BookingContextPut, auth=[{"jwtAuth": []}], responses={**PUBLIC_ERROR_RESPONSES, 200: BookingContextResponse})
    def put(self, request, **kwargs):
        data = BookingContextPut(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(mutate(request.user, self._request(**kwargs), data.validated_data))

    @extend_schema(parameters=[OpenApiParameter("intended_booking_id", int, required=False)], request=ContextCAS, auth=[{"jwtAuth": []}], responses={**PUBLIC_ERROR_RESPONSES, 200: BookingContextResponse})
    def delete(self, request, **kwargs):
        data = ContextCAS(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(mutate(request.user, self._request(**kwargs), data.validated_data, delete=True, intended=_intended(request)))
