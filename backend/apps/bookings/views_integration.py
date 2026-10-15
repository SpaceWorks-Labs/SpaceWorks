"""Server booking reads authorize by HMAC scopes, never resource/user grants."""

from django.shortcuts import get_object_or_404
from django.utils.crypto import salted_hmac
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.apiclients.read_contract import SignedReadView, keyset_page
from apps.apiclients.read_schema import HMAC_PARAMETERS, PAGE_PARAMETERS, READ_ERRORS
from apps.apiclients.scope_registry_booking_reads import ARRIVAL_READ, BOOKING_READ, RESOURCE_READ
from apps.audit.services import record
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable
from apps.tenant_migration.gate_runtime import boundary_tenant_write

from .models import BookableSpace, Booking
from .serializers_integration import (
    IntegrationBookingPageSerializer, IntegrationBookingResourcePageSerializer,
    IntegrationBookingResourceSerializer, IntegrationBookingSerializer,
)

AUTH = [{"ServerHMAC": []}]
BOOKING_DESCRIPTION = (
    "Requires bookings:read; bookings:attendance:read adds current unreversed arrived_at, "
    "including arrivals retained after completion. No contacts, answers, notes, credentials "
    "or payment data. GET and HEAD audit the disclosure under the tenant source fence."
)


class BookingIntegrationReadView(SignedReadView):
    def tenant(self, request):
        tenant = request.api_client.makerspace
        if not is_servable(tenant) or not tenant.superadmin_access_enabled:
            raise NotFound()
        if not module_enabled(tenant, "bookings") or not feature_enabled(tenant, "bookings.api_read"):
            raise NotFound()
        return tenant

    def resources(self, request):
        return BookableSpace.objects.filter(makerspace=self.tenant(request)).select_related("makerspace")

    def bookings(self, request):
        # Attribute reads must traverse the scoped PII accessor with its tenant
        # already loaded; values()/raw SQL would expose encrypted name storage.
        return Booking.objects.filter(space__makerspace=self.tenant(request)).select_related("space__makerspace")

    def reservation_response(self, request, queryset, *, subject, target=None, detail=False):
        tenant = self.tenant(request)
        with boundary_tenant_write(tenant.pk):
            attendance = ARRIVAL_READ in request.api_client.scopes
            if detail:
                rows, cursor = [get_object_or_404(queryset)], None
            else:
                rows, cursor = keyset_page(request, queryset,
                                           subject=f"{subject}:attendance:{attendance}")
            data = IntegrationBookingSerializer(rows, many=True, attendance=attendance).data
            record(None, "api_client.bookings_read", makerspace=tenant, target=target,
                   meta={"principal_fingerprint": salted_hmac(
                       "api-read", request.api_client.client_id, algorithm="sha256").hexdigest(),
                         "rows": len(rows), "attendance": attendance})
            return Response(data[0] if detail else {"next_cursor": cursor, "results": data})


class IntegrationBookingResourceListView(BookingIntegrationReadView):
    required_scopes = (RESOURCE_READ,)

    @extend_schema(tags=["Server bookings"], auth=AUTH, parameters=PAGE_PARAMETERS,
                   summary="Read tenant resources (server HMAC; booking_resources:read)",
                   responses={200: IntegrationBookingResourcePageSerializer, **READ_ERRORS})
    def get(self, request):
        rows, cursor = keyset_page(request, self.resources(request), subject="booking-resources")
        return Response({"next_cursor": cursor,
                         "results": IntegrationBookingResourceSerializer(rows, many=True).data})


class IntegrationBookingResourceDetailView(BookingIntegrationReadView):
    required_scopes = (RESOURCE_READ,)

    @extend_schema(tags=["Server bookings"], auth=AUTH, parameters=HMAC_PARAMETERS,
                   summary="Read one tenant resource (server HMAC; booking_resources:read)",
                   responses={200: IntegrationBookingResourceSerializer, **READ_ERRORS})
    def get(self, request, pk):
        return Response(IntegrationBookingResourceSerializer(get_object_or_404(self.resources(request), pk=pk)).data)


class IntegrationBookingListView(BookingIntegrationReadView):
    required_scopes = (BOOKING_READ,)

    @extend_schema(tags=["Server bookings"], auth=AUTH, parameters=PAGE_PARAMETERS,
                   summary="Read minimal tenant reservations (server HMAC; bookings:read)",
                   description=BOOKING_DESCRIPTION,
                   responses={200: IntegrationBookingPageSerializer, **READ_ERRORS})
    def get(self, request):
        return self.reservation_response(request, self.bookings(request), subject="bookings")


class IntegrationBookingDetailView(BookingIntegrationReadView):
    required_scopes = (BOOKING_READ,)

    @extend_schema(tags=["Server bookings"], auth=AUTH, parameters=HMAC_PARAMETERS,
                   summary="Read one tenant reservation (server HMAC; bookings:read)",
                   description=BOOKING_DESCRIPTION,
                   responses={200: IntegrationBookingSerializer, **READ_ERRORS})
    def get(self, request, pk):
        return self.reservation_response(request, self.bookings(request).filter(pk=pk),
                                         subject=f"booking:{pk}", detail=True)


class IntegrationBookingResourceReservationsView(BookingIntegrationReadView):
    required_scopes = (BOOKING_READ,)

    @extend_schema(tags=["Server bookings"], auth=AUTH, parameters=PAGE_PARAMETERS,
                   summary="Read reservations for one resource (server HMAC; bookings:read)",
                   description=BOOKING_DESCRIPTION,
                   responses={200: IntegrationBookingPageSerializer, **READ_ERRORS})
    def get(self, request, pk):
        resource = get_object_or_404(self.resources(request), pk=pk)
        return self.reservation_response(request, self.bookings(request).filter(space=resource),
                                         subject=f"booking-resource:{pk}:bookings", target=resource)
