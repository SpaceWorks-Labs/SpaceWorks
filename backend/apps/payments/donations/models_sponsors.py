"""Sponsors (release 2 lane L18; #94, #96, #128 C-14).

A `Sponsor` is an organisation or person backing the space, with a public face (name, logo
through the public image pipeline, tier, website, blurb) and a private contact (scoped PII).
Perks are a checklist: a tier's perks are templates copied onto each sponsor of that tier,
and every copy is fulfilled (who, when) on its own. Sponsor money is `sponsorship` income:
a `SponsorshipCharge` raises one `Payment` (no account) that staff settle offline, or pay by
an L5 pay link. Event-level sponsors stay `events.EventSponsor`; a `SponsorEventLink` points
at one, never duplicating it.
"""

from django.db import models
from django.db.models import F, Q

from apps.encryption.mappers import ScopedPiiModelMixin
from apps.payments.models_settings import currency_validator
from apps.payments.money_model import MoneyDecimalField


class SponsorTier(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="sponsor_tiers")
    name = models.CharField(max_length=80)
    rank = models.PositiveSmallIntegerField(default=0)
    amount = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="")
    description = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank", "name", "pk"]
        constraints = [models.UniqueConstraint(fields=["makerspace", "name"], name="sponsor_tier_name_unique")]


class Sponsor(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="sponsors")
    name = models.CharField(max_length=150)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    tier = models.ForeignKey(SponsorTier, null=True, blank=True, on_delete=models.SET_NULL, related_name="sponsors")
    logo_key = models.CharField(max_length=300, blank=True, default="")
    website_url = models.URLField(max_length=300, blank=True, default="")
    blurb = models.CharField(max_length=300, blank=True, default="")
    contact_name = models.TextField(blank=True, default="")
    contact_email = models.TextField(blank=True, default="")
    contact_phone = models.TextField(blank=True, default="")
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    show_on_wall = models.BooleanField(default=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(starts_on__isnull=True) | Q(ends_on__isnull=True)
                                   | Q(ends_on__gte=F("starts_on")), name="sponsor_window"),
        ]


class SponsorPerk(models.Model):
    """A tier's template perk (tier set) or one sponsor's checklist item (sponsor set)."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    tier = models.ForeignKey(SponsorTier, null=True, blank=True, on_delete=models.CASCADE, related_name="perks")
    sponsor = models.ForeignKey(Sponsor, null=True, blank=True, on_delete=models.CASCADE, related_name="perks")
    source_perk = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    description = models.CharField(max_length=300)
    due_on = models.DateField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    fulfilled_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    note = models.CharField(max_length=300, blank=True, default="")
    reminded_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_on", "pk"]
        constraints = [
            models.CheckConstraint(condition=(Q(tier__isnull=False, sponsor__isnull=True)
                                              | Q(tier__isnull=True, sponsor__isnull=False)),
                                   name="sponsor_perk_one_owner"),
            models.CheckConstraint(condition=Q(fulfilled_at__isnull=True) | Q(sponsor__isnull=False),
                                   name="sponsor_perk_fulfilled_on_sponsor"),
            models.UniqueConstraint(fields=["sponsor", "source_perk"],
                                    condition=Q(sponsor__isnull=False, source_perk__isnull=False),
                                    name="sponsor_perk_copied_once"),
        ]


class SponsorshipCharge(models.Model):
    """One agreed sponsor payment; its `Payment` (subject `sponsorship`) has no account."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    # RESTRICT, not PROTECT: a sponsor with charges is never deleted on its own (it is archived),
    # but a space purge that deletes both together may.
    sponsor = models.ForeignKey(Sponsor, on_delete=models.RESTRICT, related_name="charges")
    amount = MoneyDecimalField(max_digits=13, decimal_places=3)
    currency = models.CharField(max_length=3, validators=[currency_validator])
    description = models.CharField(max_length=200, blank=True, default="")
    # Hack-money G8: a payment may be for one event, and earmarked for that event's prize pool.
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    earmark = models.CharField(max_length=12, default="general", choices=[("general", "General"), ("prize_pool", "Prize pool")])
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="sponsorship_charge_amount_positive"),
                       models.CheckConstraint(condition=Q(earmark="general") | Q(event__isnull=False),
                                              name="sponsorship_charge_earmark_event")]


class SponsorEventLink(models.Model):
    """Links a space sponsor to an existing event-level `events.EventSponsor` row."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="event_links")
    event_sponsor = models.OneToOneField("events.EventSponsor", on_delete=models.CASCADE, related_name="space_sponsor_link")
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
