"""Booking-only worlds: no fixture or production dependency on events."""
from tests.accounts.reauth_helpers import force_recent_authenticate

from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.rbac import Action
from apps.bookings.models import BookableSpace, BookingSpaceStaffGrant
from tests.machines.certification_helpers import _bookable, _manager, _member, _space


def client_for(user):
    client = APIClient()
    force_recent_authenticate(client, user)
    return client


def grant_fixture(permission="edit_details", slug="booking-grants"):
    tenant = _space(slug, certifications=False)
    tenant.enabled_features = sorted(set(tenant.enabled_features) | {"bookings.staff_grants", "bookings.recurring"})
    tenant.save(update_fields=["enabled_features"])
    manager, role = _manager(tenant, slug + "-manager", actions=(Action.MANAGE_BOOKINGS,))
    user = User.objects.create_user(username=slug + "-grantee", password="Grant-password-123!",
                                   email=slug + "@example.test", email_verified_at=timezone.now())
    resource = _bookable(tenant)
    grant = BookingSpaceStaffGrant.objects.create(
        makerspace=tenant, space=resource, user=user, granted_by=manager, permissions=[permission],
    )
    member, membership = _member(tenant, slug + "-member")
    return tenant, manager, user, resource, grant, member


def service_manager():
    """Explicit system manager for pre-authority workflow unit tests."""
    user, _ = User.objects.get_or_create(username="booking-service-root", defaults={
        "account_kind": "platform", "is_staff": True,
        "is_superuser": True, "role": "superadmin", "access_status": "active",
    })
    return user
