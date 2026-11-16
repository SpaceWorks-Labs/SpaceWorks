"""Shared fixtures for the lane L18 local tests (untracked)."""

from decimal import Decimal

from django.utils import timezone

from apps.payments.models import Donation, DonationSettings, Payment
from tests.payments.account_helpers import make_payer
from tests.return_helpers import authenticated_client, make_member, make_space

CODE = "246810"


def switch(space, *keys, on=True):
    features = set(space.enabled_features or [])
    features = features | set(keys) if on else features - set(keys)
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_features", "updated_at"])
    return space


def setup(slug, *features):
    space = make_space(slug)
    switch(space, "finance.donations", "billing.documents", *features)
    manager = make_member(f"{slug}-sm", space)
    donor = make_payer(f"{slug}-donor", space)
    return space, manager, donor


def client(user):
    return authenticated_client(user)


def staff(slug, space, role):
    return make_member(f"{slug}-{role}", space, membership_role=role)


def tax_ready(space, *, number="AAATS1234F20240", start=None, end=None):
    switch(space, "finance.tax_exempt_receipts")
    today = timezone.localdate()
    DonationSettings.objects.update_or_create(makerspace=space, defaults={
        "tax_exempt_registration_number": number, "tax_exempt_valid_from": start or today.replace(year=today.year - 1),
        "tax_exempt_valid_until": end or today.replace(year=today.year + 2), "tax_exempt_registrant_pan": "AAATS1234F",
        # Decision 242(m): tax receipts need the non-profit profile; the old columns become its 80G entry.
        "is_nonprofit": True, "tax_exemptions": []})
    return space


def fixed_code(monkeypatch):
    """Every contact code is CODE; the mail goes nowhere."""
    monkeypatch.setattr("apps.hardware_requests.contact_verification._generate_otp", lambda: CODE)
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", lambda *args, **kwargs: True,
                        raising=False)


def give_url(space):
    return f"/api/v1/public/{space.slug}/donations/give"


def page_url(space):
    return f"/api/v1/public/{space.slug}/donations"


def admin(space, tail=""):
    return f"/api/v1/admin/makerspace/{space.pk}/donations{tail}"


def charge_for(donation):
    return Payment.objects.get(makerspace=donation.makerspace, subject_type="donation", subject_id=donation.pk)


def settle_offline(manager, payment, method="cash", reference="DESK-1"):
    response = client(manager).post(
        f"/api/v1/admin/makerspace/{payment.makerspace_id}/payments/{payment.pk}/mark-offline",
        {"settlement": {"method": method, "reference": reference,
                        "received_at": timezone.now().isoformat()}}, format="json")
    assert response.status_code == 200, response.content
    return response


def gift(space, donor, amount="500.00", **extra):
    """A signed-in member's gift through the public route."""
    response = client(donor).post(give_url(space), {"amount": amount, **extra}, format="json")
    assert response.status_code == 201, response.content
    return Donation.objects.get(pk=response.json()["id"]), response


def money(value):
    return Decimal(str(value))
