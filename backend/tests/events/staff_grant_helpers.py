"""Real event/grant fixtures shared by Lane A behavioral tests."""

from django.utils import timezone

from apps.events.models import EventStaffGrant
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event


def grant_fixture(permission="edit_details", *, slug="event-grants", grantee="event-grantee"):
    space = event_space(slug)
    manager = make_staff(space)
    user = account(grantee)
    user.set_password("staff-grant-password-123")
    user.email_verified_at = timezone.now()
    user.save(update_fields=["password", "email_verified_at"])
    event = open_event(space)
    grant = EventStaffGrant.objects.create(
        makerspace=space, event=event, user=user,
        granted_by=manager, permissions=[permission],
    )
    from apps.events.contributions.models_roles import EventGrantEntitlement
    EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
        source_kind="manual", permissions=[permission], created_by=manager)
    return space, manager, user, event, grant


def set_grant_permissions(grant, permissions):
    """Change a manual grant the way the grant service does.

    Authority is read from the live manual `EventGrantEntitlement`; the grant's
    own `permissions` column is only the display union of its sources.
    """
    from apps.events.contributions.grant_sources import write_union
    from apps.events.contributions.models_roles import EventGrantEntitlement
    live = EventGrantEntitlement.objects.filter(grant=grant, source_kind="manual", revoked_at__isnull=True)
    creator = live.values_list("created_by", flat=True).first() or grant.granted_by_id
    live.update(revoked_at=timezone.now())
    if permissions:
        EventGrantEntitlement.objects.create(
            event_id=grant.event_id, series_id=grant.series_id, makerspace_id=grant.makerspace_id,
            grant=grant, source_kind="manual", permissions=sorted(permissions), created_by_id=creator,
        )
    write_union(grant)
    grant.refresh_from_db()
