"""Release 0.12.0 UI lanes U1/U2 gaps: dues currency, waiver for pass holders, minors consent id,
volunteer-credit member name."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces import guest_pass_issue, minors
from apps.makerspaces.member_dashboard_service import membership_dues
from apps.makerspaces.models import (
    CommunityPolicy, GuardianConsent, MakerspaceMembership, MakerspaceWaiver, VolunteerCredit,
)
from apps.payments.models import MakerspacePaymentSettings
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_guest_passes import _space as pass_space
from tests.makerspaces.test_membership_j1 import manager, member_role, space, user
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _member(makerspace, name):
    person = user(name)
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace, user=person, assigned_role=member_role(makerspace), role="custom", status="active",
        activated_at=timezone.now() - timedelta(days=60))
    return person, membership


def test_dues_payload_names_the_currency_the_dues_charge_uses():
    makerspace = space("dues-cur")
    makerspace.membership_dues_amount = Decimal("25.00")
    makerspace.save(update_fields=["membership_dues_amount"])
    _, membership = _member(makerspace, "dues-member")
    assert membership_dues(membership)["dues_currency"] == MakerspacePaymentSettings.for_makerspace(makerspace).default_currency
    MakerspacePaymentSettings.objects.create(makerspace=makerspace, default_currency="inr")
    assert membership_dues(membership)["dues_currency"] == "inr"
    assert membership_dues(membership)["dues_amount"] == "25.00"


def test_live_guest_pass_holder_reads_the_waiver_but_a_stranger_does_not():
    makerspace = pass_space("wv-pass")
    MakerspaceWaiver.objects.create(makerspace=makerspace, version="v1", body="Sign here", is_active=True)
    holder, stranger = user("wv-holder"), user("wv-stranger")
    guest_pass_issue.issue_staff_pass(manager(makerspace, "wv-desk"), makerspace, holder)
    url = reverse("member-waiver", kwargs={"makerspace_id": makerspace.pk})
    body = authenticated_client(holder).get(url).json()
    assert body["has_waiver"] is True and body["version"] == "v1" and body["body"] == "Sign here"
    assert authenticated_client(stranger).get(url).status_code == 404


def test_staff_minor_row_carries_the_current_consent_id_version_and_signed_at():
    makerspace = space("minor-cid")
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "minors")
    CommunityPolicy.objects.create(makerspace=makerspace, minors_admitted=True)
    staff, child = manager(makerspace, "minor-staff"), user("minor-child")
    minors.publish_terms(staff, makerspace, "I consent.", "v1")
    today = timezone.localdate()
    profile = minors.record_minor(staff, makerspace, child, date_of_birth=today.replace(year=today.year - 15, day=1).isoformat())
    url = reverse("admin-minors", kwargs={"makerspace_id": makerspace.pk})
    assert authenticated_client(staff).get(url).json()["results"][0]["current_consent_id"] is None
    consent = minors.sign_consent(staff, profile, "A Guardian", accepted=True, method=GuardianConsent.Method.STAFF_RECORDED)
    row = authenticated_client(staff).get(url).json()["results"][0]
    assert row["current_consent_id"] == consent.pk
    assert row["current_consent_version"] == "v1" and row["current_consent_signed_at"]


def test_staff_volunteer_credit_rows_carry_member_name():
    makerspace = space("vol-name")
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "volunteer_credit")
    staff = manager(makerspace, "vol-staff")
    person, _ = _member(makerspace, "vol-member")
    person.display_name = "Vera Volunteer"
    person.save(update_fields=["display_name"])
    VolunteerCredit.objects.create(makerspace=makerspace, member=person, kind="discount", amount=Decimal("5.00"),
                                   currency="usd", status="available")
    rows = authenticated_client(staff).get(
        reverse("admin-volunteer-credits", kwargs={"makerspace_id": makerspace.pk})).json()["results"]
    assert rows[0]["member_name"] == "Vera Volunteer"
