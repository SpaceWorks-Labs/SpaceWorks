"""Makerspace archive and recovery lifecycle."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit import services as audit
from apps.makerspaces.servability import is_servable
from .lifecycle_authority import require_platform_superadmin


def archive_impact(makerspace):
    """Unsettled money that archiving this makerspace would make harder to reach."""
    from apps.payments.models import Payment

    owned_pending = Payment.objects.filter(
        makerspace=makerspace,
        status=Payment.Status.PENDING,
    ).count()
    routed_pending = Payment.objects.filter(
        via_makerspace=makerspace,
        status=Payment.Status.PENDING,
    ).exclude(makerspace=makerspace).count()
    # Event payout obligations are money the space owes members. Recording a payout
    # needs a servable space, so archiving pauses settlement until it is restored.
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    unpaid_event_payouts = EventPayoutObligation.objects.filter(
        makerspace=makerspace, state="open", approved_minor__gt=0,
    ).count()
    return {
        "owned_pending": owned_pending,
        "routed_pending": routed_pending,
        "total_pending": owned_pending + routed_pending,
        "unpaid_event_payouts": unpaid_event_payouts,
    }


def archive(makerspace, actor):
    from apps.makerspaces.archive_requests import direct_archive

    return direct_archive(makerspace, actor)


def _archive_locked(makerspace, actor, *, archived_at):
    if not is_servable(makerspace):
        raise ValidationError(gettext("Makerspace is not available for archival."))

    # This is an advisory snapshot: payment creation does not universally take
    # this lock, so a concurrent insert can change the count before commit.
    impact = archive_impact(makerspace)
    makerspace.archived_at = archived_at
    makerspace.archived_by = actor
    makerspace.public_inventory_enabled = False
    makerspace.save(
        update_fields=["archived_at", "archived_by", "public_inventory_enabled"]
    )
    audit.record(
        actor,
        "makerspace.archived",
        makerspace=makerspace,
        target=makerspace,
        meta=impact,
    )
    return makerspace


def unarchive(makerspace, actor):
    require_platform_superadmin(actor)
    with transaction.atomic():
        locked = makerspace.__class__.objects.select_for_update().get(pk=makerspace.pk)
        if locked.archived_at is None:
            raise ValidationError(gettext("Makerspace is not archived."))
        from apps.tenant_migration.cutover import has_active_migrated_out_handoff

        if has_active_migrated_out_handoff(locked.pk):
            raise ValidationError(
                gettext("A migrated-out makerspace can only be reopened with a signed abort receipt.")
            )

        locked.archived_at = None
        locked.archived_by = None
        locked.save(update_fields=["archived_at", "archived_by"])
        audit.record(actor, "makerspace.unarchived", makerspace=locked, target=locked)
        return locked
