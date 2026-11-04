"""Per-event delegates who receive registration staff notices (not tenant staff)."""

from django.db.models import Q

from .event_permissions import MANAGE_REGISTRATIONS


def _grant_rows(event):
    from .models import EventStaffGrant
    return EventStaffGrant.objects.filter(
        Q(event=event) | Q(series_id=event.series_id, series__isnull=False),
        makerspace_id=event.makerspace_id, revoked_at__isnull=True,
        permissions__contains=[MANAGE_REGISTRATIONS],
    )


def registration_grantees(event):
    from apps.accounts.models import User
    return User.objects.filter(
        pk__in=_grant_rows(event).values("user_id"), is_active=True, access_status="active",
        is_tenant_dump_stub=False,
    ).order_by("pk")


def holds_registration_grant(user_id, event):
    """Live re-check at send time; event_authority also applies module and servability gates."""
    from apps.accounts.models import User
    from . import event_authority
    user = User.objects.filter(pk=user_id).first()
    return bool(user and event_authority.can(user, event, MANAGE_REGISTRATIONS))
