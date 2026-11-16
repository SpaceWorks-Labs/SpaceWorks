"""Granting and revoking machine access (decision 319): authority, validation, audit, notice.

Authority is the existing machine authority, never a new role: the Space Manager (and superadmin)
may grant anything; a Machine Manager only inside their machine scope (`access.is_machine_admin` for a
machine, `access.can_create_machine` -- the TYPE link -- for a type-wide grant, so being handed one
machine is not authority over its whole class). Cross-tenant ids are a 404 at the view.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import MakerspaceMembership
from . import access
from .models import MachineAccessGrant
from .notifications_machine_access import notify_access


def can_grant(actor, makerspace, *, machine=None, machine_type=None):
    if machine is not None:
        return access.is_machine_admin(actor, machine)
    return machine_type is not None and access.can_create_machine(actor, makerspace.pk, machine_type)


def manageable_grants(actor, rows):
    """The grants in ``rows`` the actor may manage: the same per-machine / per-type authority as granting.

    Memoised per machine and per type, so a list of N grants costs one authority check per distinct target.
    Shared by the staff list and the ``machine-access-grants`` report, so a Machine Manager never sees, or
    counts, grants outside their machine scope.
    """
    memo = {}

    def ok(row):
        key = (row.makerspace_id, "m", row.machine_id) if row.machine_id else (row.makerspace_id, "t", row.machine_type_id)
        if key not in memo:
            memo[key] = can_grant(actor, row.makerspace, machine=row.machine, machine_type=row.machine_type)
        return memo[key]
    return [row for row in rows if ok(row)]


def _validated(actor, makerspace, member, machine, machine_type, expires_at):
    require_module(makerspace, "machines")
    if (machine is None) == (machine_type is None):
        raise ValidationError(gettext("Choose either one machine or one machine type."))
    if machine is not None and machine.makerspace_id != makerspace.pk:
        raise ValidationError({"machine_id": gettext("Unknown machine.")})
    if machine_type is not None and machine_type.makerspace_id not in (None, makerspace.pk):
        raise ValidationError({"machine_type_id": gettext("Unknown machine type.")})
    if not can_grant(actor, makerspace, machine=machine, machine_type=machine_type):
        raise PermissionDenied()
    if not MakerspaceMembership.objects.filter(makerspace=makerspace, user=member, status="active").exists():
        raise ValidationError({"member_id": gettext("An active member of this makerspace is required.")})
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError({"expires_at": gettext("Expiry must be in the future.")})


@transaction.atomic
def grant_access(actor, makerspace, member, *, machine=None, machine_type=None, expires_at=None, note=""):
    """Grant (or renew the live grant of) `member` on one machine or one machine type."""
    _validated(actor, makerspace, member, machine, machine_type, expires_at)
    # Serialise grants for one member in one space on their membership row, so two concurrent grants
    # renew one live row instead of the loser hitting the unique constraint (a 500).
    MakerspaceMembership.objects.select_for_update().filter(makerspace=makerspace, user=member).first()
    # Scoped to the space (336k/M8): a built-in machine type is shared, and space B must never renew,
    # re-note or reveal the live grant space A holds for the same member.
    existing = MachineAccessGrant.objects.select_for_update().filter(
        makerspace=makerspace, member=member, machine=machine, machine_type=machine_type,
        revoked_at__isnull=True).first()
    meta = {"member_id": member.pk, "machine_id": getattr(machine, "pk", None),
            "machine_type_id": getattr(machine_type, "pk", None),
            "expires_at": expires_at.isoformat() if expires_at else None}
    if existing is not None:
        existing.expires_at, existing.note, existing.expiry_notice_sent_at = expires_at, str(note)[:1000], None
        existing.save(update_fields=["expires_at", "note", "expiry_notice_sent_at"])
        record(actor, "machine_access.renewed", makerspace=makerspace, target=existing, meta=meta)
        notify_access(existing, "granted")
        return existing
    row = MachineAccessGrant.objects.create(
        makerspace=makerspace, member=member, machine=machine, machine_type=machine_type, granted_by=actor,
        expires_at=expires_at, note=str(note)[:1000])
    record(actor, "machine_access.granted", makerspace=makerspace, target=row, meta=meta)
    notify_access(row, "granted")
    return row


@transaction.atomic
def revoke_access(actor, grant, *, reason=""):
    row = MachineAccessGrant.objects.select_for_update(of=("self",)).select_related(
        "machine", "machine_type", "makerspace").get(pk=grant.pk)
    if not can_grant(actor, row.makerspace, machine=row.machine, machine_type=row.machine_type):
        raise PermissionDenied()
    if row.revoked_at is not None:
        return row
    row.revoked_at, row.revoked_by = timezone.now(), actor
    row.save(update_fields=["revoked_at", "revoked_by"])
    record(actor, "machine_access.revoked", makerspace=row.makerspace, target=row,
           meta={"member_id": row.member_id, "reason": str(reason)[:500]})
    notify_access(row, "revoked")
    return row


def bulk_grant(actor, makerspace, members, *, machine=None, machine_type=None, expires_at=None, note=""):
    """Grant to many members; each is its own transaction so one refusal never hides the others."""
    done, failed = [], []
    for member in members:
        try:
            done.append(grant_access(actor, makerspace, member, machine=machine, machine_type=machine_type,
                                     expires_at=expires_at, note=note))
        except (ValidationError, PermissionDenied) as refused:
            failed.append({"member_id": member.pk, "detail": str(getattr(refused, "detail", refused))})
    return done, failed
