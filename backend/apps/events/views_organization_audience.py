"""Private eligibility advisory; registration always rechecks under the source locks."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.models import MakerspaceWaiver
from .capacity import registration_is_open
from .organization_audience import AUDIENCE, OrganizationAudienceRefused, require_organization_audience
from .serializers_organization_audience import EventEligibilitySerializer, HostWaiverProjectionSerializer
from .views_public import _public_events


class EventOrganizationEligibilityView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Cookie, Authorization"
        return response

    @extend_schema(
        tags=["Public events"], summary="Read private organization audience eligibility",
        description="Account-specific advisory only, private/no-store. Owned live registrations may renew host consent after signup closes, until the event ends. No membership or eligibility-source identities. Admission rechecks all proofs and current host consent transactionally.",
        request=None, responses={200: EventEligibilitySerializer,
                                 **{code: ErrorSerializer for code in (400, 401, 403, 404, 429)}},
    )
    def get(self, request, makerspace_slug, public_token):
        from django.utils import timezone
        space = get_public_makerspace(makerspace_slug)
        require_module_for_servable(space, "events")
        event = get_object_or_404(_public_events(space), public_token=public_token)
        eligible, reason = True, None
        try:
            require_organization_audience(event, request.user)
        except OrganizationAudienceRefused as exc:
            eligible, reason = False, str(exc.detail["code"])
        waiver = MakerspaceWaiver.objects.filter(makerspace=space, is_active=True).first() if event.registration_audience == AUDIENCE else None
        consent_repair_required = False
        if waiver and eligible:
            from .host_waivers import HostWaiverRequired, require_host_waiver
            from .models import EventRegistration
            own_row = EventRegistration.objects.filter(event=event, member=request.user).first()
            try:
                require_host_waiver(event, request.user, registration=own_row)
            except HostWaiverRequired:
                consent_repair_required = bool(own_row and own_row.status in (
                    EventRegistration.Status.REGISTERED, EventRegistration.Status.WAITLISTED,
                    EventRegistration.Status.PENDING_APPROVAL,
                ) and timezone.now() < event.ends_at)
            else:
                waiver = None
        if not eligible:
            waiver = None
        # Cutoff forbids new admission, but cannot strand an owner needing renewed consent.
        if not registration_is_open(event, timezone.now()):
            eligible, reason = False, "registration_closed"
            if not consent_repair_required:
                waiver = None
        response = Response({"eligible": eligible, "reason": reason,
                             "consent_repair_required": consent_repair_required,
                             "host_waiver": HostWaiverProjectionSerializer(waiver).data if waiver else None})
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Cookie, Authorization"
        return response
