"""Tinkerspace donations, sponsors and calendar sync (release 2 L18, #134 walkthrough), through the real services.

Turns on donations (pledges and 80G receipts too), sponsors and the new calendar feeds, and
seeds a laser-cutter campaign with one gift received at the desk and one monthly pledge, a
Gold sponsor tier with a perk, a sponsor on it and that sponsor's agreed payment.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.payments.donations import pledges, services, sponsors
from apps.payments.donations.identity import Donor
from apps.payments.models import DonationCampaign, DonationSettings, SponsorPerk, SponsorTier

FEATURES = ("finance.donations", "finance.recurring_donations", "finance.tax_exempt_receipts", "finance.sponsors",
            "events.shifts_feed", "events.public_feed", "calendar.combined_feed", "charges.enabled")


def _donor(user):
    return Donor(account=user, name=getattr(user, "display_name", "") or user.username, email=user.email, actor=user)


def seed_donations(space, manager, members):
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    space.save(update_fields=["enabled_features"])
    today = timezone.localdate()
    DonationSettings.objects.update_or_create(makerspace=space, defaults={
        "page_intro": "Every gift keeps the doors open and the tools sharp.", "suggested_amounts": ["500", "1000", "2500"],
        "tax_exempt_registration_number": "AAATT1234TE20251", "tax_exempt_valid_from": today - timedelta(days=200),
        "tax_exempt_valid_until": today + timedelta(days=900), "tax_exempt_registrant_pan": "AAATT1234T",
        "is_nonprofit": True, "legal_name": f"{space.name} Trust", "signatory_name": "Treasurer",
        "signatory_title": "Treasurer", "tax_exemptions": [], "updated_by": manager})
    currency = services.space_currency(space)
    campaign = DonationCampaign.objects.create(
        makerspace=space, name="A new laser cutter", slug="laser-cutter", currency=currency,
        description="Help us replace the old CO2 laser.", goal_amount=Decimal("150000"), created_by=manager)
    givers = list(members.values())
    services.record_desk_gift(space, _donor(givers[0]), actor=manager, amount=Decimal("2500"), campaign=campaign,
                              settlement={"method": "cash", "reference": "DESK-0001",
                                          "received_at": timezone.now() - timedelta(days=2)})
    pledges.create_pledge(space, _donor(givers[1 % len(givers)]), amount=Decimal("500"), interval="monthly",
                          campaign=campaign)
    tier = SponsorTier.objects.create(makerspace=space, name="Gold", rank=1, amount=Decimal("100000"),
                                      currency=currency, description="Logo on the wall and the event banners.")
    SponsorPerk.objects.create(makerspace=space, tier=tier, description="Logo on the build-night banner",
                               due_on=today + timedelta(days=10))
    sponsor = sponsors.save_sponsor(space, actor=manager, data={
        "name": "Circuit Supply Co.", "tier": tier, "website_url": "https://example.com/circuit-supply",
        "blurb": "Parts for every project.", "contact_name": "Priya Raman", "contact_email": "priya@example.com",
        "starts_on": today - timedelta(days=30), "ends_on": today + timedelta(days=335)})
    sponsors.raise_charge(sponsor, actor=manager, amount=Decimal("100000"), description="Gold sponsorship 2026")
    return campaign
