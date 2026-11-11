"""Separate manual authority from role/shift sources and their display union."""
from django.utils import timezone
from apps.audit.services import record
from apps.events.models_staff_grants import EventStaffGrant
from apps.events.programme_locks import assert_lock_context
from .models_roles import EventGrantEntitlement


def write_union(grant):
    union = sorted({permission for permissions in EventGrantEntitlement.objects.filter(
        grant=grant, revoked_at__isnull=True).values_list("permissions", flat=True) for permission in permissions})
    grant.permissions = union
    grant.save(update_fields=["permissions"])


def manual_changed(*, grant, permissions, actor, operation):
    from apps.events.programme_locks import current_locks
    assert_lock_context(current_locks(grant.event_id or 0))
    existing = EventGrantEntitlement.objects.select_for_update().filter(
        grant=grant, source_kind="manual", revoked_at__isnull=True).first()
    desired = [] if operation == "revoke_grant" else sorted(permissions)
    from apps.events import staff_grant_limits as limits
    limit = limits.current_limit() if operation == "redeem_invite" else None
    tracks, starts, ends = (limit if limit and limits.is_limited(limit) else ([], None, None))
    carried = (existing.track_ids, existing.valid_from, existing.valid_until) if existing else ([], None, None)
    if operation == "redeem_invite" and existing:
        if limits.is_limited(limit) and carried != (tracks, starts, ends):
            # Merging a limited invite into a differently limited source would widen one of them.
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "This person already holds a differently limited grant here."})
        desired = sorted(set(desired) | set(existing.permissions))
    elif operation != "redeem_invite" and existing:
        tracks, starts, ends = carried  # an edit never silently widens a limited source
    if existing and (existing.permissions != desired or not desired):
        existing.revoked_at, existing.revoked_by = timezone.now(), actor
        existing.save(update_fields=["revoked_at", "revoked_by"])
        record(actor, "event.entitlement.revoked", makerspace=grant.makerspace, target=existing,
            meta={"source_kind": "manual"})
        existing = None
    if desired and existing is None:
        source = EventGrantEntitlement.objects.create(grant=grant, event_id=grant.event_id,
            series_id=grant.series_id, makerspace_id=grant.makerspace_id, source_kind="manual",
            permissions=desired, track_ids=tracks, valid_from=starts, valid_until=ends, created_by=actor)
        record(actor, "event.entitlement.created", makerspace=grant.makerspace, target=source,
            meta={"source_kind": "manual", "permissions": desired})
    write_union(grant)


class GrantSources:
    def ensure_container_locked(self, *, event_id, member_id, actor_id, locks):
        assert_lock_context(locks)
        from apps.events.models import Event
        event = Event.objects.get(pk=event_id)
        if member_id not in locks.account_ids or actor_id not in locks.account_ids:
            raise RuntimeError("Declare contributor and issuer before event locks.")
        row = EventStaffGrant.objects.select_for_update().filter(event_id=event_id,
            makerspace_id=event.makerspace_id, user_id=member_id, revoked_at__isnull=True).first()
        if row is None:
            row = EventStaffGrant.objects.create(event_id=event_id, makerspace_id=event.makerspace_id,
                user_id=member_id, permissions=[], granted_by_id=actor_id)
            record(None, "event.staff_grant_container_created", makerspace=event.makerspace, target=row)
        return row.pk

    def write_display_union_locked(self, *, grant_id, permissions, actor_id, locks):
        assert_lock_context(locks)
        row = EventStaffGrant.objects.select_for_update().get(pk=grant_id)
        write_union(row)
