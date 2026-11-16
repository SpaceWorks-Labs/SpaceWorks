"""Decision 223 (k): staff routes to book a space for an organization's partner event (lane L3b).

`manage_reservations` on the space, and the `bookings.organization_bookings` switch (404 while off). The
booking is made for the organization's contact member and recorded against the organization; see
`organization_booking` for the billing rule. The picker route lists only organizations linked to the
space together with the members who may act as contact (active in the organization AND at the space).
"""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.bookings.organization_booking import book_for_organization, organization_bookings_on
from apps.bookings.serializers_admin import BookingAdminSerializer
from apps.bookings.views_admin_booking_create import ERRORS
from apps.bookings.views_admin_spaces import manageable_space
from apps.makerspaces.guards import feature_off
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models import Payment
from django.utils.translation import gettext

TAG = "Admin bookings"


class OrganizationContactSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    name = serializers.CharField()


class OrganizationChoiceSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    name = serializers.CharField()
    contacts = OrganizationContactSerializer(many=True)


class OrganizationBookingInputSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField(min_value=1)
    contact_member_id = serializers.IntegerField(min_value=1, help_text="The organization's member the debt is recorded against.")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    note = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    custom_answers = serializers.JSONField(required=False)


def _space(request, pk):
    space = manageable_space(request.user, pk, "manage_reservations")
    if not organization_bookings_on(space.makerspace):
        raise feature_off("bookings.organization_bookings")
    return space


class OrganizationBookingChoicesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Organizations that can book this space",
                   description="Needs manage_reservations and bookings.organization_bookings. Active "
                               "organizations linked to the space, with the members who may be the contact.",
                   responses={200: OrganizationChoiceSerializer(many=True), **ERRORS})
    def get(self, request, pk):
        from apps.organizations.models import OrganizationMakerspace, OrganizationMembership
        space = _space(request, pk)
        space_members = set(MakerspaceMembership.objects.filter(
            makerspace_id=space.makerspace_id, status="active").values_list("user_id", flat=True))
        links = (OrganizationMakerspace.objects.filter(makerspace_id=space.makerspace_id, organization__is_active=True)
                 .select_related("organization").order_by("organization__name"))
        result = []
        for link in links[:100]:
            org = link.organization
            people = OrganizationMembership.objects.filter(
                organization=org, status="active", user_id__in=space_members).select_related("user")
            result.append({"organization_id": org.pk, "name": org.name, "contacts": [
                {"member_id": m.user_id, "name": m.user.display_name or m.user.get_full_name() or m.user.username}
                for m in people[:100]]})
        return Response(result)


class OrganizationBookingCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="Book this space for an organization's partner event",
                   request=OrganizationBookingInputSerializer, responses={201: BookingAdminSerializer, **ERRORS},
                   description="Made for the contact member and recorded against the organization. The debt "
                               "follows the ordinary booking charge path against the contact (organizations "
                               "have no ledger account); the booking uses none of the contact's plan hours.")
    def post(self, request, pk):
        from apps.organizations.models import Organization
        space = _space(request, pk)
        data = OrganizationBookingInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        organization = Organization.objects.filter(pk=values.pop("organization_id")).first()
        contact = User.objects.filter(pk=values.pop("contact_member_id")).first()
        # A missing organization/contact answers exactly like an unlinked/ineligible one (the same 400),
        # so the route cannot be used to probe which organization or user ids exist.
        if organization is None:
            raise ValidationError({"organization_id": gettext("This organization is not linked to this space.")})
        if contact is None:
            raise ValidationError({"contact_member_id": gettext("The contact must be an active member of the organization.")})
        booking = book_for_organization(request.user, space, organization, contact, **values)
        context = scoped_payment_context(
            request.user, rbac.Action.MANAGE_BOOKINGS, Payment.SubjectType.BOOKING, [booking.pk])
        return Response(BookingAdminSerializer(booking, context=context).data, status=201)
