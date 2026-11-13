"""HMAC server reads have scope authority; user/resource grants are irrelevant."""

from django.db.models import Case, DateTimeField, OuterRef, Subquery, Value, When
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.apiclients.read_contract import SignedReadView, keyset_page
from apps.apiclients.scope_registry_reads import ATTENDANCE_READ, EVENT_READ, PARTICIPANT_READ
from apps.audit.services import record
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable
from apps.tenant_migration.gate_runtime import boundary_tenant_write

from .models import Event, EventCheckInEvent, EventRegistration
from .serializers_integration import (
    IntegrationEventPageSerializer, IntegrationEventSerializer,
    IntegrationParticipantPageSerializer, IntegrationParticipantSerializer,
)

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=description) for code, description in (
    (400, "Invalid cursor or page size."), (401, "Missing or invalid HMAC signature."),
    (403, "Server type, tenant binding or required scopes missing."),
    (404, "Tenant/event/module/feature unavailable."), (429, "Read rate exceeded."),
    (423, "Source tenant is frozen; audited reads cannot append history."),
    (503, "Source gate could not be proven available."),
)}
HMAC_PARAMETERS = [
    OpenApiParameter("X-Client-Id", str, location="header", required=True),
    OpenApiParameter("X-Timestamp", str, location="header", required=True),
    OpenApiParameter("X-Nonce", str, location="header", description="Required when nonce enforcement is enabled."),
]
PAGE_PARAMETERS = HMAC_PARAMETERS + [OpenApiParameter("cursor", str, description="Opaque, signed continuation cursor."),
                   OpenApiParameter("page_size", int, description="1–200; default 100.")]


class EventIntegrationReadView(SignedReadView):
    required_scopes = (EVENT_READ,)

    def tenant(self, request):
        tenant = request.api_client.makerspace
        if not is_servable(tenant):
            raise NotFound()
        if not module_enabled(tenant, "events") or not feature_enabled(tenant, "events.api_read"):
            raise NotFound()
        return tenant

    def event(self, request, pk):
        return get_object_or_404(Event.objects.select_related("makerspace"),
                                 pk=pk, makerspace=self.tenant(request))


class IntegrationEventListView(EventIntegrationReadView):
    @extend_schema(tags=["Server events"], auth=[{"ServerHMAC": []}],
                   summary="Read minimal tenant events (server HMAC; events:read)",
                   parameters=PAGE_PARAMETERS, responses={200: IntegrationEventPageSerializer, **ERRORS})
    def get(self, request):
        rows, cursor = keyset_page(request, Event.objects.filter(makerspace=self.tenant(request)),
                                   subject="events")
        return Response({"next_cursor": cursor, "results": IntegrationEventSerializer(rows, many=True).data})


class IntegrationEventDetailView(EventIntegrationReadView):
    @extend_schema(tags=["Server events"], auth=[{"ServerHMAC": []}],
                   summary="Read one tenant event (server HMAC; events:read)", parameters=HMAC_PARAMETERS,
                   responses={200: IntegrationEventSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(IntegrationEventSerializer(self.event(request, pk)).data)


class IntegrationEventParticipantsView(EventIntegrationReadView):
    required_scopes = (EVENT_READ, PARTICIPANT_READ)

    @extend_schema(tags=["Server events"], auth=[{"ServerHMAC": []}], parameters=PAGE_PARAMETERS,
                   summary="Read minimal participants; events:read AND participants:read required",
                   description="Attendance dates are included only with participants:attendance:read. "
                               "No contacts, answers, ticket/check-in tokens or payment fields.",
                   responses={200: IntegrationParticipantPageSerializer, **ERRORS})
    def get(self, request, pk):
        event = self.event(request, pk)
        # This GET appends a disclosure audit. Hold the source fence so a capture
        # cannot freeze tenant history between projection and audit insertion.
        with boundary_tenant_write(event.makerspace_id):
            attendance = ATTENDANCE_READ in request.api_client.scopes
            rows = EventRegistration.objects.filter(event=event).select_related("event")
            if attendance:
                latest = EventCheckInEvent.objects.filter(registration_id=OuterRef("pk")).order_by(
                    "-attended_at", "-pk").values("attended_at")[:1]
                rows = rows.annotate(api_attended_at=Case(
                    When(status=EventRegistration.Status.ATTENDED, then=Subquery(latest)),
                    default=Value(None), output_field=DateTimeField(),
                ))
            rows, cursor = keyset_page(request, rows, subject=f"event:{event.pk}:participants:{attendance}")
            # Reading model attributes uses ScopedPiiModelMixin; values()/raw SQL would
            # expose ciphertext when scoped encryption is enabled.
            data = IntegrationParticipantSerializer(rows, many=True, attendance=attendance).data
            from django.utils.crypto import salted_hmac
            record(None, "api_client.participants_read", makerspace=event.makerspace, target=event,
                   meta={"principal_fingerprint": salted_hmac("api-read", request.api_client.client_id,
                                                              algorithm="sha256").hexdigest(),
                         "rows": len(rows), "attendance": attendance})
            return Response({"next_cursor": cursor, "results": data})
