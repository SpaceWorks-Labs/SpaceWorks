"""Recurring donations: a pledge raises one gift (and one charge) each period (#128 C-14c).

No card is stored and nothing is taken automatically: each period's charge waits for the
giver to pay it (online, or offline with a receipt), exactly like a membership renewal.
The raise is idempotent -- one gift per (pledge, period), unique in the database -- and a
period missed while the switch was off is skipped, never charged later.
"""

import logging

from dateutil.relativedelta import relativedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from .gates import DonationRefused

from apps.audit import services as audit

from .models import Donation, DonationPledge

logger = logging.getLogger(__name__)
STEP = {"monthly": relativedelta(months=1), "quarterly": relativedelta(months=3), "yearly": relativedelta(years=1)}


def next_period(day, interval):
    return day + STEP[interval]


@transaction.atomic
def create_pledge(space, donor, *, amount, interval, starts_on=None, campaign=None, tax=(False, "", "")):
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    from .services import space_currency, tax_detail_for

    assert_write_allowed(space.pk)
    if interval not in STEP:
        raise DonationRefused("Choose monthly, quarterly or yearly.", "interval_invalid", "interval")
    today = timezone.localdate()
    starts_on = max(starts_on or today, today)
    wants, pan, address = tax
    pledge = DonationPledge(
        makerspace=space, campaign=campaign, donor=donor.account, donor_name=donor.name, donor_email=donor.email,
        amount=amount, currency=space_currency(space), interval=interval, starts_on=starts_on,
        next_due_on=starts_on, wants_tax_receipt=wants, tax_detail=tax_detail_for(space, pan, address) if wants else None,
        created_by=donor.actor)
    pledge.save()
    audit.record(donor.account, "pledge.created", makerspace=space, target=pledge, meta={
        "pledge_id": pledge.pk, "amount": str(amount), "currency": pledge.currency, "interval": interval,
        "guest": donor.is_guest, "campaign_id": getattr(campaign, "pk", None)})
    return pledge


@transaction.atomic
def change_pledge(pledge, *, actor, action, amount=None, interval=None):
    """pause / resume / cancel / update (amount, interval) -- audited `pledge.<action>`."""
    locked = DonationPledge.objects.select_for_update().get(pk=pledge.pk)
    if locked.status == DonationPledge.Status.CANCELLED:
        raise DonationRefused("This pledge is cancelled.", "pledge_cancelled")
    fields = ["updated_at"]
    if action == "cancel":
        locked.status, locked.cancelled_at = DonationPledge.Status.CANCELLED, timezone.now()
        fields += ["status", "cancelled_at"]
    elif action == "pause":
        locked.status = DonationPledge.Status.PAUSED
        fields.append("status")
    elif action == "resume":
        locked.status = DonationPledge.Status.ACTIVE
        # A resumed pledge never back-charges the periods it was paused for.
        today = timezone.localdate()
        while locked.next_due_on < today:
            locked.next_due_on = next_period(locked.next_due_on, locked.interval)
        fields += ["status", "next_due_on"]
    elif action == "update":
        if amount is not None:
            locked.amount = amount
            fields.append("amount")
        if interval is not None:
            if interval not in STEP:
                raise DonationRefused("Choose monthly, quarterly or yearly.", "interval_invalid", "interval")
            locked.interval = interval
            fields.append("interval")
    else:
        raise DonationRefused("Unknown pledge action.", "pledge_action_invalid", "action")
    locked.save(update_fields=fields)
    if action == "cancel":
        audit.record(actor, "pledge.cancelled", makerspace=locked.makerspace, target=locked,
                     meta={"pledge_id": locked.pk, "status": locked.status})
    elif action == "pause":
        audit.record(actor, "pledge.paused", makerspace=locked.makerspace, target=locked,
                     meta={"pledge_id": locked.pk, "status": locked.status})
    elif action == "resume":
        audit.record(actor, "pledge.resumed", makerspace=locked.makerspace, target=locked,
                     meta={"pledge_id": locked.pk, "status": locked.status})
    else:
        audit.record(actor, "pledge.updated", makerspace=locked.makerspace, target=locked,
                     meta={"pledge_id": locked.pk, "status": locked.status})
    return locked


def raise_period(pledge, today):
    """Raise the gift for the pledge's due period (at most one), then advance. Returns the gift or None."""
    from .identity import Donor
    from .services import create_gift

    with transaction.atomic():
        locked = DonationPledge.objects.select_for_update().select_related("makerspace").get(pk=pledge.pk)
        if (locked.status != DonationPledge.Status.ACTIVE or locked.next_due_on > today
                or (locked.ends_on and locked.next_due_on > locked.ends_on)):
            return None
        period = locked.next_due_on
        # Missed periods (the switch was off, the job did not run) are skipped, never back-charged.
        while next_period(locked.next_due_on, locked.interval) <= today:
            locked.next_due_on = next_period(locked.next_due_on, locked.interval)
            period = locked.next_due_on
        if locked.ends_on and period > locked.ends_on:
            return None
        donor = Donor(account=locked.donor, name=locked.donor_name, email=locked.donor_email,
                      actor=locked.created_by)
        gift = None
        if not Donation.objects.filter(pledge=locked, period_start=period).exists():
            try:
                with transaction.atomic():
                    gift, _payment = create_gift(
                        locked.makerspace, donor, amount=locked.amount, campaign=locked.campaign,
                        tax=(locked.wants_tax_receipt, "", ""), tax_detail=locked.tax_detail,
                        source=Donation.Source.PLEDGE, pledge=locked, period_start=period, actor=locked.created_by)
            except IntegrityError:
                gift = None
        locked.next_due_on = next_period(period, locked.interval)
        locked.last_reminded_on = today if gift else locked.last_reminded_on
        locked.save(update_fields=["next_due_on", "last_reminded_on", "updated_at"])
        if gift is not None:
            audit.record(None, "pledge.period_raised", makerspace=locked.makerspace, target=locked, meta={
                "pledge_id": locked.pk, "donation_id": gift.pk, "period_start": period.isoformat()})
            from .notices import notify_pledge_due
            notify_pledge_due(locked, gift)
    return gift


def due_pledge_ids(limit, today):
    return list(DonationPledge.objects.filter(status=DonationPledge.Status.ACTIVE, next_due_on__lte=today)
                .order_by("next_due_on", "pk").values_list("pk", flat=True)[:limit])


def raise_one(pledge_id, today):
    """One pledge in its own tenant write boundary, only while the space's switch is on."""
    from apps.makerspaces.platform import feature_enabled
    from apps.tenant_migration.gate_runtime import tenant_write

    pledge = DonationPledge.objects.select_related("makerspace").get(pk=pledge_id)
    if not feature_enabled(pledge.makerspace, "finance.recurring_donations"):
        return None
    with tenant_write(pledge.makerspace_id):
        return raise_period(pledge, today)
