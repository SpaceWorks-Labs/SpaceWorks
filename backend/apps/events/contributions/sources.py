"""C owns entitlement synchronization; shared infrastructure owns grant containers."""
from django.db import connection
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.accounts.models import User
from apps.audit.services import record
from apps.events import event_authority
from apps.events.contracts.services import DelegationScope
from .authority import can_delegate_helpers
from .errors import ProgrammeError
from .models_roles import EventRoleAssignment, EventGrantEntitlement, EventSponsorTrack
from .models_shifts import EventShiftSignup
from .ports import ports

ROLE_PERMISSIONS = {"mentor": ("mentor_queue",), "judge": ("judge",),
                    "sponsor_rep": ("view_sponsor_track",), "volunteer": ()}


def _require_locks(row, locks):
    if not connection.in_atomic_block or row.event_id != locks.event_id or row.makerspace_id not in locks.tenant_ids:
        raise RuntimeError("Entitlements require the workflow's event and host locks.")


def _sync(*, row, kind, desired, actor_id, locks, starts=None, ends=None, tracks=()):
    _require_locks(row, locks)
    actor = get_object_or_404(User, pk=actor_id) if actor_id is not None else None
    source = {"role_assignment" if kind == "role" else "shift_signup": row}
    existing = EventGrantEntitlement.objects.select_for_update().filter(
        event_id=row.event_id, source_kind=kind, revoked_at__isnull=True, **source).first()
    grant_id = existing.grant_id if existing else None
    same = existing and (existing.permissions == sorted(desired) and existing.track_ids == sorted(tracks)
        and existing.valid_from == starts and existing.valid_until == ends)
    if existing and not same:
        existing.revoked_at, existing.revoked_by = timezone.now(), actor
        existing.save(update_fields=["revoked_at", "revoked_by"])
        record(actor, "event.entitlement.revoked", makerspace=existing.makerspace, target=existing,
               meta={"source_kind": kind, "event_id": row.event_id})
    if desired and not same:
        grant_id = ports().grants.ensure_container_locked(event_id=row.event_id,
            member_id=row.member_id, actor_id=actor_id, locks=locks)
        from apps.events.models import EventStaffGrant
        get_object_or_404(EventStaffGrant, pk=grant_id, event_id=row.event_id,
            makerspace_id=row.makerspace_id, user_id=row.member_id, revoked_at__isnull=True)
        entitlement = EventGrantEntitlement.objects.create(event_id=row.event_id, makerspace_id=row.makerspace_id,
            grant_id=grant_id, source_kind=kind, **source, permissions=sorted(desired),
            track_ids=sorted(tracks), valid_from=starts, valid_until=ends, created_by=actor)
        record(actor, "event.entitlement.created", makerspace=entitlement.makerspace, target=entitlement,
               meta={"source_kind": kind, "event_id": row.event_id, "permissions": sorted(desired)})
    if grant_id:
        # Future shift sources keep their container alive. The display union is
        # never an authority predicate; live source queries apply the time window.
        union = sorted({permission for permissions in EventGrantEntitlement.objects.filter(
            grant_id=grant_id, revoked_at__isnull=True)
            .values_list("permissions", flat=True) for permission in permissions})
        ports().grants.write_display_union_locked(grant_id=grant_id, permissions=tuple(union), actor_id=actor_id, locks=locks)


def sync_role_locked(*, assignment_id, actor_id, locks):
    row = get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=locks.event_id)
    if actor_id is None:
        actor_id = row.approved_by_id
    desired = tuple(row.delegated_permissions or ROLE_PERMISSIONS.get(row.role, ())) if (
        row.state == "approved" and not row.imported_inert) else ()
    if desired:
        actor = get_object_or_404(User, pk=actor_id)
        if row.role == "co_organizer":
            event_authority.require(actor, row.event, None)
            if not all(event_authority.can(actor, row.event, p) for p in desired):
                raise ProgrammeError("permission_subset", "Role permissions exceed current authority.", status=403)
        elif not can_delegate_helpers(actor=actor, target=row.event, permissions=desired,
            scope=DelegationScope(event_id=row.event_id, helper_role=row.role, track_ids=tuple(row.track_ids))):
            raise ProgrammeError("permission_subset", "Role permissions exceed current helper authority.", status=403)
        if row.role == "sponsor_rep":
            allowed = set(EventSponsorTrack.objects.filter(event_id=row.event_id,
                sponsor_id=row.sponsor_id, track__event_id=row.event_id).values_list("track_id", flat=True))
            if not row.track_ids or not set(row.track_ids) <= allowed:
                raise ProgrammeError("invalid_tracks", "Select only this sponsor's event tracks.", status=400)
    _sync(row=row, kind="role", desired=desired, tracks=row.track_ids, actor_id=actor_id, locks=locks)


def sync_shift_locked(*, signup_id, actor_id, locks):
    row = get_object_or_404(EventShiftSignup, pk=signup_id, event_id=locks.event_id)
    shift, assignment = row.shift, row.assignment
    desired = tuple(shift.permission_preset) if (row.state == "approved" and shift.state == "open"
        and assignment.state == "approved" and not assignment.imported_inert
        and not row.attendance.state in ("checked_out", "no_show")) else ()
    # Earlier approvals verified the preset subset; later sync only narrows it.
    if desired and not set(desired) <= set(shift.posting.permission_preset):
        raise ProgrammeError("permission_subset", "Shift permissions exceed the posting preset.", status=403)
    _sync(row=row, kind="shift", desired=desired, actor_id=actor_id, locks=locks,
          starts=shift.starts_at, ends=shift.ends_at)
