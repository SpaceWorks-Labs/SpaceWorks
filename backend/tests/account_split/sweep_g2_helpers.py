"""Principal factories for event/booking account-split regression fixtures."""

from apps.accounts.models import User
from tests.account_split.p1_helpers import staff


def staff_user(space, username, *, staff_role="space_manager", **fields):
    """Build complete tenant staff authority without promoting a member."""
    aliases = {"print_manager": "machine_manager", "guest_admin": "handover"}
    staff_role = aliases.get(staff_role, staff_role)
    fields.setdefault("access_status", User.AccessStatus.ACTIVE)
    fields.pop("role", None)
    if staff_role == "custom":
        user = User.objects.create_user(username=username, **fields)
        from apps.makerspaces.models import MakerspaceMembership
        MakerspaceMembership.objects.create(user=user, makerspace=space, role="custom",
                                            assigned_role=space.roles.get(slug="member"))
        return user
    return staff(space, username, role=staff_role, **fields)[0]


def service_manager():
    user = User.objects.filter(username="booking-service-root").first()
    if user is None:
        user = User.objects.create_superuser(username="booking-service-root", password=None)
    return user


def ledger_booking():
    """Keep borrowers as members; create a separate actor for staff workflows."""
    from tests.bookings.payment_ledger_helpers import ledger_booking as original
    space, room, member, _ = original.__wrapped__()
    manager = staff_user(space, "bk0-staff-manager")
    return space, room, member, manager
