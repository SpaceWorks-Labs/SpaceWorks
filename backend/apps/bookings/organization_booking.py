"""Decision 223 (k), lane L3b: an organization books a space for a partner event.

Billing. Organizations have no ledger account of their own (`Payment.member` is a person, and
`apps.organizations` carries only a billing e-mail), so the booking is made for the organization's named
CONTACT MEMBER: the ordinary charge path records the debt against that member exactly like a member booking
(recorded first, independent of the payments rail), the booking draws nothing from the contact's plan hours,
and `BookingOrganizationLink` records WHICH organization the booking was for. When organizations later get a
ledger, `billed_member` is the single seam to replace.

Rules. Needs `bookings.organization_bookings`, `manage_reservations` (checked by `create_booking`), an
active organization linked to this space, and a contact who holds an active membership in the organization
AND at the space. Reports, calendars and the booking list read the name through `organization_name_for`.
"""
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from apps.bookings.models import BookableSpace, BookingOrganizationLink
from apps.makerspaces.guards import feature_off
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import feature_enabled
from django.utils.translation import gettext

FEATURE = "bookings.organization_bookings"


def organization_bookings_on(makerspace):
    return feature_enabled(makerspace, FEATURE)


def _validated(space, organization, contact):
    from apps.organizations.derived_membership import is_org_member
    from apps.organizations.models import OrganizationMakerspace
    if not organization.is_active or not OrganizationMakerspace.objects.filter(
            organization=organization, makerspace_id=space.makerspace_id).exists():
        raise ValidationError({"organization_id": gettext("This organization is not linked to this space.")})
    # Decision 293/295: an organization workspace's own members are members of the organization.
    if not is_org_member(contact, organization):
        raise ValidationError({"contact_member_id": gettext("The contact must be an active member of the organization.")})
    if not MakerspaceMembership.objects.filter(
            makerspace_id=space.makerspace_id, user=contact, status="active").exists():
        raise ValidationError({"contact_member_id": gettext("The contact must be an active member of this space.")})


def link_organization(booking, organization, contact, actor):
    """Called by `create_booking` inside its transaction, right after the booking row exists."""
    link = BookingOrganizationLink.objects.create(
        booking=booking, makerspace=booking.space.makerspace, organization=organization,
        organization_name=organization.name[:200], billed_member=contact, created_by=actor)
    # The booking is the audit target: the link row itself is omitted from tenant dumps.
    audit.record(actor, "booking.organization_linked", makerspace=booking.space.makerspace, target=booking,
                 meta={"organization_id": organization.pk})
    return link


def book_for_organization(actor, space, organization, contact, **booking_values):
    """Create the booking for `contact` on behalf of `organization`. `booking_values` are the usual
    `create_booking` keywords (starts_at, ends_at, note, custom_answers, ...)."""
    from apps.bookings import services
    if not organization_bookings_on(space.makerspace):
        raise feature_off(FEATURE)
    if actor is None:
        raise PermissionDenied()
    locked = BookableSpace.objects.select_related("makerspace").get(pk=space.pk)
    _validated(locked, organization, contact)
    with transaction.atomic():
        return services.create_booking(
            locked, member=contact, actor=actor, organization=organization, **booking_values)


def organization_name_for(booking):
    """The organization a booking was made for, or None. Safe to call for any booking."""
    return organization_names([booking.pk]).get(booking.pk)


def organization_names(booking_ids):
    """`{booking_id: organization_name}` for a page of bookings (reports, calendars, lists).

    Decision 218: while `bookings.organization_bookings` is off for a booking's space the name is not
    shown anywhere; the link rows are kept and show again on re-enable."""
    rows = list(BookingOrganizationLink.objects.filter(booking_id__in=list(booking_ids))
                .select_related("makerspace"))
    live = {}
    for row in rows:
        if row.makerspace_id not in live:
            live[row.makerspace_id] = organization_bookings_on(row.makerspace)
    return {row.booking_id: row.organization_name for row in rows if live[row.makerspace_id]}
