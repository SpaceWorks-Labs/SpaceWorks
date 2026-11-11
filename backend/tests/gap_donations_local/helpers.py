"""Shared fixtures for the RP-3 donations report tests (local only, never committed)."""

from apps.makerspaces.models import MakerspaceRole
from apps.payments.models import DonationCampaign
from tests.accounts.account_factories import make_staff
from tests.l18_local.helpers import charge_for, client, gift, settle_offline, setup, staff, switch

PAN = "ABCDE1234F"
KEYS = ("donations-campaign-progress", "donations-pledges", "donations-sponsor-perks", "finance-donations")


def report_space(slug, *features):
    """A space with reports on, donations on and the given extra switches."""
    space, manager, donor = setup(slug, "finance.ledger", *features)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"reports"})
    space.save(update_fields=["enabled_modules", "updated_at"])
    return space, manager, donor


def finance_staff(slug, space):
    """A custom role holding only view_finance (finance staff, #100)."""
    MakerspaceRole.objects.get_or_create(makerspace=space, slug="finance-view",
                                         defaults={"name": "Finance viewer", "granted_actions": ["view_finance"]})
    return make_staff(space, username=f"{slug}-finance", role_slug="finance-view", email=f"{slug}-fin@e.com")


def campaign(space, name="New laser", slug="laser", goal="1000.00", **extra):
    return DonationCampaign.objects.create(makerspace=space, name=name, slug=slug, currency="inr",
                                           goal_amount=goal, **extra)


def paid_gift(space, manager, donor, amount, **extra):
    donation, _ = gift(space, donor, amount=amount, **extra)
    settle_offline(manager, charge_for(donation), reference=f"DESK-{donation.pk}")
    donation.refresh_from_db()
    return donation


def analytics(user, space, key, **params):
    return client(user).get(f"/api/v1/admin/makerspace/{space.pk}/analytics/{key}", params)


def export_csv(user, space, key):
    response = client(user).get(f"/api/v1/admin/makerspace/{space.pk}/reports/{key}/export", {"format": "csv"})
    body = b"".join(response.streaming_content) if getattr(response, "streaming", False) else response.content
    return response, body.decode("utf-8", errors="ignore")


def rows_as_dicts(payload):
    header, *rows = payload["rows"]
    return [dict(zip(header, row)) for row in rows]


__all__ = ["KEYS", "PAN", "analytics", "campaign", "client", "export_csv", "finance_staff", "gift", "paid_gift",
           "report_space", "rows_as_dicts", "staff", "switch"]
