"""Staff price preview: authorize room, member and window before showing the bindable quote."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import feature_off
from apps.presence.guard import require_active_member

from .serializers_staff_booking import StaffBookingQuoteInputSerializer, StaffBookingQuoteSerializer
from .staff_price_confirmation import preview
from .views_admin_booking_create import ERRORS, _members
from .views_admin_spaces import manageable_space
from django.utils.translation import gettext


class StaffBookingQuoteView(APIView):
    """No write and no audit: the preview is a read the locked create re-verifies."""

    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'], summary='Preview the room price a staff booking will charge',
        description='Requires `manage_reservations` on the room and an active local member with a '
                    'current waiver. Send `price_confirmation` back on create; a moved price, '
                    'member, window or charge mode answers 409 `price_changed`.',
        request=StaffBookingQuoteInputSerializer,
        responses={200: StaffBookingQuoteSerializer, **ERRORS,
                   423: OpenApiResponse(ErrorSerializer, description='Tenant frozen for migration.')},
    )
    def post(self, request, pk):
        space = manageable_space(request.user, pk, "manage_reservations")
        body = StaffBookingQuoteInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        values = body.validated_data
        membership = get_object_or_404(_members(request.user, space), user_id=values['member_id'])
        require_active_member(membership.user, space.makerspace)
        from .included_hours import event_venue_exempt
        from .models import Booking
        original = None
        if values.get('replaces_booking_id'):
            original = get_object_or_404(Booking.objects.select_related('space'), pk=values['replaces_booking_id'],
                                         space__makerspace_id=space.makerspace_id)
            manageable_space(request.user, original.space_id, "manage_reservations")
        exempt = event_venue_exempt(space, membership.user, request.user, original)
        organization = None
        if values.get('organization_id') is not None:
            from .organization_booking import organization_bookings_on
            if not organization_bookings_on(space.makerspace):
                raise feature_off('bookings.organization_bookings')
            exempt = True  # 223(k): an organization's booking draws no plan hours, as create does
            # B13: its hours come from the organization's bank; an unlinked id answers like create does.
            from apps.organizations.models import Organization, OrganizationMakerspace
            organization = Organization.objects.filter(
                pk=values['organization_id'], is_active=True,
                pk__in=OrganizationMakerspace.objects.filter(makerspace_id=space.makerspace_id).values('organization_id'),
            ).first()
            if organization is None:
                raise ValidationError({'organization_id': gettext('This organization is not linked to this space.')})
        data = preview(space, membership.user, values['starts_at'], values['ends_at'], exempt, organization)
        return Response(StaffBookingQuoteSerializer(data).data,
                        headers={'Cache-Control': 'private, no-store'})
