"""Sponsor services: the sponsor row, perk checklists, sponsorship money and event links.

Every change is audited (`sponsor.*`, `perk.*`). Sponsorship money is ONE `Payment` per
`SponsorshipCharge` (subject `sponsorship`, no account, raised by staff), so it is income in
the ledger's `donations` domain, settled offline with a receipt or paid through an L5 pay link.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .models import Sponsor, SponsorEventLink, SponsorPerk, SponsorshipCharge, SponsorTier

def _changed(before, after):
    return sorted(key for key in after if before.get(key) != after[key])


@transaction.atomic
def save_sponsor(space, *, actor, data, sponsor=None):
    """Create or update. Contact fields are scoped PII and never enter the audit row."""
    tier = data.get("tier")
    if tier is not None and tier.makerspace_id != space.pk:
        raise ValidationError({"tier": "That tier is not in this space."})
    creating = sponsor is None
    sponsor = sponsor or Sponsor(makerspace=space, created_by=actor)
    before = {key: getattr(sponsor, key, None) for key in data}
    old_tier = sponsor.tier_id
    for key, value in data.items():
        setattr(sponsor, key, value)
    sponsor.save()
    if creating:
        audit.record(actor, "sponsor.created", makerspace=space, target=sponsor,
                     meta={"sponsor_id": sponsor.pk, "fields": sorted(data)})
    else:
        audit.record(actor, "sponsor.updated", makerspace=space, target=sponsor,
                     meta={"sponsor_id": sponsor.pk, "fields": _changed(before, data)})
    if sponsor.tier_id and sponsor.tier_id != old_tier:
        copy_tier_perks(sponsor, actor=actor)
    return sponsor


@transaction.atomic
def archive_sponsor(sponsor, *, actor, archived=True):
    sponsor.archived_at = timezone.now() if archived else None
    sponsor.save(update_fields=["archived_at", "updated_at"])
    if archived:
        audit.record(actor, "sponsor.archived", makerspace=sponsor.makerspace, target=sponsor,
                     meta={"sponsor_id": sponsor.pk})
    else:
        audit.record(actor, "sponsor.restored", makerspace=sponsor.makerspace, target=sponsor,
                     meta={"sponsor_id": sponsor.pk})
    return sponsor


def copy_tier_perks(sponsor, *, actor):
    """A tier's template perks become this sponsor's own checklist items, once each."""
    copied = 0
    for template in SponsorPerk.objects.filter(tier_id=sponsor.tier_id, sponsor__isnull=True):
        _row, created = SponsorPerk.objects.get_or_create(
            sponsor=sponsor, source_perk=template,
            defaults={"makerspace_id": sponsor.makerspace_id, "description": template.description,
                      "due_on": template.due_on})
        copied += created
    if copied:
        audit.record(actor, "perk.copied", makerspace=sponsor.makerspace, target=sponsor,
                     meta={"sponsor_id": sponsor.pk, "tier_id": sponsor.tier_id, "count": copied})
    return copied


@transaction.atomic
def save_perk(space, *, actor, data, perk=None):
    owner = data.get("sponsor") or data.get("tier") or (perk.sponsor if perk else None) or (perk.tier if perk else None)
    if owner is None or owner.makerspace_id != space.pk:
        raise ValidationError({"detail": "A perk belongs to one sponsor or one tier in this space."})
    creating = perk is None
    perk = perk or SponsorPerk(makerspace=space)
    for key, value in data.items():
        setattr(perk, key, value)
    perk.save()
    if creating:
        audit.record(actor, "perk.created", makerspace=space, target=perk,
                     meta={"perk_id": perk.pk, "sponsor_id": perk.sponsor_id, "tier_id": perk.tier_id})
    else:
        audit.record(actor, "perk.updated", makerspace=space, target=perk,
                     meta={"perk_id": perk.pk, "sponsor_id": perk.sponsor_id, "tier_id": perk.tier_id})
    return perk


@transaction.atomic
def fulfil_perk(perk, *, actor, fulfilled=True, note=""):
    if perk.sponsor_id is None:
        raise ValidationError({"detail": "Tier perks are templates; fulfil a sponsor's copy.",
                               "code": "perk_is_template"})
    perk.fulfilled_at, perk.fulfilled_by = (timezone.now(), actor) if fulfilled else (None, None)
    perk.note = (note or perk.note or "")[:300]
    perk.save(update_fields=["fulfilled_at", "fulfilled_by", "note"])
    if fulfilled:
        audit.record(actor, "perk.fulfilled", makerspace=perk.makerspace, target=perk,
                     meta={"perk_id": perk.pk, "sponsor_id": perk.sponsor_id})
    else:
        audit.record(actor, "perk.reopened", makerspace=perk.makerspace, target=perk,
                     meta={"perk_id": perk.pk, "sponsor_id": perk.sponsor_id})
    return perk


@transaction.atomic
def raise_charge(sponsor, *, actor, amount, description=""):
    """Record what the sponsor agreed to pay: one account-less charge staff raised."""
    from apps.payments.models import Payment
    from apps.payments.services import create_payment

    from .services import space_currency

    space = sponsor.makerspace
    charge = SponsorshipCharge.objects.create(makerspace=space, sponsor=sponsor, amount=amount,
                                              currency=space_currency(space), description=description[:200],
                                              created_by=actor)
    payment = create_payment(makerspace=space, subject_type=Payment.SubjectType.SPONSORSHIP, subject_id=charge.pk,
                             member=None, amount=amount, currency=charge.currency, created_by=actor,
                             subject_label=f"Sponsorship: {sponsor.name}"[:255])
    audit.record(actor, "sponsor.charge_raised", makerspace=space, target=charge, meta={
        "sponsor_id": sponsor.pk, "charge_id": charge.pk, "payment_id": payment.pk, "amount": str(amount)})
    return charge, payment


@transaction.atomic
def link_event_sponsor(sponsor, event_sponsor, *, actor):
    if event_sponsor.makerspace_id != sponsor.makerspace_id:
        raise ValidationError({"event_sponsor": "That event sponsor is not in this space."})
    link, created = SponsorEventLink.objects.get_or_create(
        event_sponsor=event_sponsor, defaults={"makerspace_id": sponsor.makerspace_id, "sponsor": sponsor,
                                               "created_by": actor})
    if not created and link.sponsor_id != sponsor.pk:
        raise ValidationError({"event_sponsor": "That event sponsor is already linked to another sponsor.",
                               "code": "event_sponsor_linked"})
    if created:
        audit.record(actor, "sponsor.event_linked", makerspace=sponsor.makerspace, target=sponsor,
                     meta={"sponsor_id": sponsor.pk, "event_sponsor_id": event_sponsor.pk,
                           "event_id": event_sponsor.event_id})
    return link


@transaction.atomic
def unlink_event_sponsor(link, *, actor):
    sponsor_id, event_sponsor_id, space = link.sponsor_id, link.event_sponsor_id, link.sponsor.makerspace
    link.delete()
    audit.record(actor, "sponsor.event_unlinked", makerspace=space, target=space,
                 meta={"sponsor_id": sponsor_id, "event_sponsor_id": event_sponsor_id})


def tiers(space):
    return SponsorTier.objects.filter(makerspace=space)
