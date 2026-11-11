"""Decision 223: guest-pass routes (staff desk, sponsor, holder, public): scoping, switches, privacy."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.models import DayPassProduct, GuestPass, GuestPassPolicy, MakerspaceMembership
from tests.makerspaces.l4_helpers import features_off, features_on, space_with_manager
from tests.makerspaces.test_membership_j1 import member_role, user
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def _on(makerspace):
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    GuestPassPolicy.objects.get_or_create(makerspace=makerspace, defaults={"sponsor_must_be_present": False})
    return features_on(makerspace, "guest_passes", "day_passes")


def _member(makerspace, name):
    person = user(name)
    MakerspaceMembership.objects.create(
        makerspace=makerspace, user=person, assigned_role=member_role(makerspace), role="custom",
        status="active", activated_at=timezone.now() - timedelta(days=60))
    return person


def test_every_staff_route_is_404_while_the_capability_is_off():
    makerspace, manager = space_with_manager("gp-api-off")
    client = authenticated_client(manager)
    for name in ("admin-guest-passes", "admin-guest-pass-policy", "admin-day-pass-products"):
        assert client.get(reverse(name, args=[makerspace.pk])).status_code == 404


def test_staff_issue_list_policy_and_revoke_round_trip():
    makerspace, manager = space_with_manager("gp-api-staff")
    _on(makerspace)
    guest = user("visitor")
    client = authenticated_client(manager)
    created = client.post(reverse("admin-guest-passes", args=[makerspace.pk]), {"holder_email": guest.email},
                          format="json")
    assert created.status_code == 201
    body = created.json()
    assert body["kind"] == "day" and body["status"] == "issued" and body["holder_id"] == guest.pk
    listed = client.get(reverse("admin-guest-passes", args=[makerspace.pk]) + "?status=issued").json()
    assert [row["id"] for row in listed["results"]] == [body["id"]]
    policy_url = reverse("admin-guest-pass-policy", args=[makerspace.pk])
    assert client.patch(policy_url, {"guest_machine_mode": "supervised"}, format="json").json()[
        "guest_machine_mode"] == "supervised"
    revoked = client.post(reverse("admin-guest-pass-revoke", args=[makerspace.pk, body["id"]]),
                          {"reason": "test"}, format="json")
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"


def test_another_spaces_staff_and_plain_members_are_refused():
    makerspace, _ = space_with_manager("gp-api-scope")
    other_space, other_manager = space_with_manager("gp-api-other")
    _on(makerspace)
    url = reverse("admin-guest-passes", args=[makerspace.pk])
    assert authenticated_client(other_manager).get(url).status_code in (403, 404)
    assert authenticated_client(_member(makerspace, "plain")).get(url).status_code in (403, 404)
    assert other_space.pk != makerspace.pk


def test_sponsor_answers_202_whether_or_not_the_email_has_an_account():
    makerspace, _ = space_with_manager("gp-api-sponsor")
    _on(makerspace)
    sponsor, guest = _member(makerspace, "sponsor"), user("visitor")
    client = authenticated_client(sponsor)
    url = reverse("member-sponsored-guests", args=[makerspace.pk])
    known = client.post(url, {"email": guest.email}, format="json")
    unknown = client.post(url, {"email": "nobody-here@example.test"}, format="json")
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    rows = client.get(url).json()
    assert len(rows) == 1 and set(rows[0]) == {"id", "guest_name", "pass_date", "status", "items_outstanding"}


def test_holder_sees_only_their_own_passes_and_must_accept_the_waiver_explicitly():
    makerspace, manager = space_with_manager("gp-api-holder")
    _on(makerspace)
    guest, other = user("visitor"), user("other-visitor")
    staff = authenticated_client(manager)
    for person in (guest, other):
        staff.post(reverse("admin-guest-passes", args=[makerspace.pk]), {"holder_email": person.email}, format="json")
    client = authenticated_client(guest)
    mine = client.get(reverse("member-guest-passes", args=[makerspace.pk])).json()
    assert len(mine["passes"]) == 1 and "should_prompt_join" in mine
    pass_id = mine["passes"][0]["id"]
    accept = reverse("member-guest-pass-waiver", args=[makerspace.pk, pass_id])
    assert client.post(accept, {"accepted": False}, format="json").status_code == 400
    assert authenticated_client(other).post(accept, {"accepted": True}, format="json").status_code == 404


def test_public_day_passes_list_name_and_price_only_and_404_when_off():
    makerspace = make_space("gp-api-public")
    _on(makerspace)
    DayPassProduct.objects.create(makerspace=makerspace, name="Drop in", amount=0, daily_cap=3, is_public=True)
    DayPassProduct.objects.create(makerspace=makerspace, name="Hidden", amount=0, is_public=False)
    url = reverse("public-day-passes", args=[makerspace.slug])
    rows = authenticated_client(user("anon-reader")).get(url).json()
    assert [set(row) for row in rows] == [{"id", "name", "amount", "currency"}]
    features_off(makerspace, "day_passes")
    assert authenticated_client(user("anon-reader-2")).get(url).status_code == 404


def test_day_pass_purchase_needs_the_switch_and_issues_a_free_pass():
    makerspace = make_space("gp-api-buy")
    _on(makerspace)
    product = DayPassProduct.objects.create(makerspace=makerspace, name="Free day", amount=0)
    guest = user("buyer")
    response = authenticated_client(guest).post(
        reverse("member-day-pass-purchase", args=[makerspace.pk, product.pk]), {}, format="json")
    assert response.status_code == 201 and response.json()["payment_id"] is None
    assert GuestPass.objects.filter(makerspace=makerspace, holder=guest, kind="day").count() == 1


def test_staff_cannot_name_another_tenants_account_by_id():
    """Final audit 0.12.0: holder_id resolves only people already tied to this space."""
    makerspace, manager = space_with_manager("gp-api-idor")
    _on(makerspace)
    stranger = user("gp-idor-stranger")
    staff = authenticated_client(manager)
    url = reverse("admin-guest-passes", args=[makerspace.pk])
    refused = staff.post(url, {"holder_id": stranger.pk}, format="json")
    assert refused.status_code == 404
    assert stranger.email not in refused.content.decode()
    assert not GuestPass.objects.filter(holder=stranger).exists()
    # Once tied to the space (here by an emailed pass) the id resolves.
    assert staff.post(url, {"holder_email": stranger.email}, format="json").status_code in {200, 201}
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    assert staff.post(url, {"holder_id": stranger.pk, "day": tomorrow}, format="json").status_code in {200, 201}
