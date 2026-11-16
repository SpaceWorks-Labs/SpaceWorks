from datetime import timedelta
from django.utils import timezone

from apps.accounts.rbac import Action
from apps.bookings.models import Booking
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

KEYS = ("booking-resource-utilization", "booking-resource-utilization-pdf", "booking-reservations", "booking-answers")
FEATURES = ("bookings.analytics", "bookings.utilization_pdf", "bookings.exports")


def fixture(slug="booking-reports"):
    tenant, manager, grantee, resource, grant, member = grant_fixture("manage_reservations", slug)
    tenant.enabled_modules = sorted(set(tenant.enabled_modules) | {"reports"})
    tenant.enabled_features = sorted(set(tenant.enabled_features) | set(FEATURES) | {"reports.saved_views"})
    tenant.timezone = "Asia/Kolkata"
    tenant.save(update_fields=["enabled_modules", "enabled_features", "timezone"])
    return tenant, manager, grantee, resource, grant, member


def auditor(tenant, user):
    """Member helpers receive tenant audit authority through an organization grant."""
    organization = Organization.objects.create(name=f"{tenant.slug} audit", slug=f"{tenant.slug}-audit")
    OrganizationMakerspace.objects.create(
        organization=organization, makerspace=tenant, relationship="owner",
    )
    return OrganizationMembership.objects.create(
        organization=organization, user=user, granted_actions=[Action.VIEW_AUDIT],
    )


def filters(resource):
    return {"subject_kind": "bookable_space", "subject_id": resource.pk}


def period(resource):
    return {**filters(resource), "start": "2026-10-01", "end": "2026-10-31"}


def booking(resource, **kwargs):
    start = timezone.now() + timedelta(days=1)
    return Booking.objects.create(space=resource, name="Booker Café α", email="booker@example.test", phone="123",
        starts_at=kwargs.pop("starts_at", start), ends_at=kwargs.pop("ends_at", start + timedelta(hours=2)),
        status=kwargs.pop("status", "confirmed"), **kwargs)
