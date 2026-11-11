"""Open item B13: staff and org-admin reads and writes of an organization's hours bank.

The booking price path lives in `organization_hours`; this module is what the API routes call. Every write runs
in one transaction under the allowance row lock, is appended to the ledger (never edited) and is audited.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.encryption.write_fence import assert_mapped_write_allowed

from .models_organization_hours import OrganizationHoursAllowance, OrganizationHoursLedger
from .organization_hours import bank, period_ends_at, period_key, totals

Entry = OrganizationHoursLedger.Entry


def state(makerspace, organization, at=None):
    """The current-period balance, derived from the ledger. `configured` is False until staff set an allowance."""
    at = at or timezone.now()
    allowance = bank(makerspace, organization)
    period = allowance.period if allowance else OrganizationHoursAllowance.Period.NONE
    key = period_key(period, at)
    pool, used = totals(makerspace, organization, key)
    return {
        "organization_id": organization.pk, "makerspace_id": getattr(makerspace, "pk", makerspace),
        "configured": allowance is not None,
        "allowance_minutes": allowance.allowance_minutes if allowance else 0, "period": period,
        "period_key": key, "period_ends_at": period_ends_at(period, at) or None,
        "pool_minutes": pool, "used_minutes": used, "remaining_minutes": max(0, pool - used),
    }


def ledger_rows(makerspace, organization):
    return OrganizationHoursLedger.objects.filter(
        makerspace=makerspace, organization=organization).select_related("actor")


def update_allowance(makerspace, organization, actor, *, allowance_minutes=None, period=None):
    """Create or change the base allowance. Takes effect for bookings made from now on; held hours stay held."""
    with transaction.atomic():
        assert_mapped_write_allowed(makerspace.pk)
        row = OrganizationHoursAllowance.objects.select_for_update().filter(
            makerspace=makerspace, organization=organization).first()
        previous = (row.allowance_minutes, row.period) if row else (0, OrganizationHoursAllowance.Period.NONE)
        if row is None:
            row = OrganizationHoursAllowance(makerspace=makerspace, organization=organization)
        if allowance_minutes is not None:
            row.allowance_minutes = allowance_minutes
        if period is not None:
            row.period = period
        row.updated_by = actor
        row.save()
        audit.record(actor, "organization.hours_allowance_updated", makerspace=makerspace, target=row,
                     meta={"organization_id": organization.pk, "allowance_minutes": row.allowance_minutes,
                           "period": row.period, "previous_allowance_minutes": previous[0],
                           "previous_period": previous[1]})
    return row


def adjust(makerspace, organization, actor, *, entry, minutes, reason):
    """Append a staff grant (positive top-up) or signed adjustment; never lets the period balance go negative."""
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    if entry == Entry.GRANT and minutes <= 0:
        raise ValidationError({"minutes": "A grant must be a positive number of minutes."})
    if minutes == 0:
        raise ValidationError({"minutes": "Enter a non-zero number of minutes."})
    with transaction.atomic():
        assert_mapped_write_allowed(makerspace.pk)
        allowance = OrganizationHoursAllowance.objects.select_for_update().filter(
            makerspace=makerspace, organization=organization).first()
        if allowance is None:
            raise ValidationError({"organization_id": "Set an allowance before granting or adjusting hours."})
        key = period_key(allowance.period, timezone.now())
        pool, used = totals(makerspace, organization, key)
        if pool + minutes - used < 0:
            raise ValidationError({"minutes": "This would take the balance below zero."})
        row = OrganizationHoursLedger.objects.create(
            makerspace=makerspace, organization=organization, entry=entry, minutes=minutes, period_key=key,
            reason=reason[:500], actor=actor)
        audit.record(actor, "organization.hours_adjusted", makerspace=makerspace, target=row,
                     meta={"organization_id": organization.pk, "entry": entry, "minutes": minutes})
    return row
