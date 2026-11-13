"""L18 sponsors: CRUD and audit, tier perks, sponsorship income, the public wall (public fields only)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.models import Payment, Sponsor, SponsorPerk
from tests.l18_local.helpers import client, setup, staff, switch

pytestmark = pytest.mark.django_db


def url(space, tail=""):
    return f"/api/v1/admin/makerspace/{space.pk}/sponsors{tail}"


def _sponsor(space, manager, **extra):
    response = client(manager).post(url(space), {
        "name": "Acme Robotics", "website_url": "https://acme.example", "blurb": "Motors for every bot",
        "contact_name": "Rita Contact", "contact_email": "rita@acme.example", "contact_phone": "+919900000000",
        **extra}, format="json")
    assert response.status_code == 201, response.content
    return Sponsor.objects.get(pk=response.json()["id"])


def test_sponsors_are_off_by_default_and_finance_only():
    space, manager, donor = setup("sp-off")
    assert client(manager).get(url(space)).status_code == 404
    switch(space, "finance.sponsors")
    assert client(manager).get(url(space)).status_code == 200
    machine = staff("sp-off", space, "machine_manager")
    assert client(machine).get(url(space)).status_code == 404


def test_tier_perks_become_each_sponsors_checklist_and_fulfilment_is_audited():
    space, manager, donor = setup("sp-perks", "finance.sponsors")
    tier = client(manager).post(url(space, "/tiers"), {"name": "Gold", "rank": 1, "amount": "100000"},
                                format="json").json()
    template = client(manager).post(url(space, "/perks"), {"tier": tier["id"], "description": "Logo on banner",
                                                          "due_on": str(timezone.localdate() + timedelta(days=3))},
                                    format="json")
    assert template.status_code == 201
    sponsor = _sponsor(space, manager, tier=tier["id"])
    item = SponsorPerk.objects.get(sponsor=sponsor)
    assert item.description == "Logo on banner" and item.source_perk_id == template.json()["id"]
    template_tick = client(manager).post(url(space, f"/perks/{template.json()['id']}/fulfil"), {}, format="json")
    assert template_tick.status_code == 400
    done = client(manager).post(url(space, f"/perks/{item.pk}/fulfil"), {"note": "Printed"}, format="json")
    assert done.status_code == 200 and done.json()["fulfilled_at"] and done.json()["fulfilled_by"] == manager.pk
    assert set(AuditLog.objects.values_list("action", flat=True)) >= {
        "sponsor.tier_created", "perk.created", "sponsor.created", "perk.copied", "perk.fulfilled"}


def test_sponsorship_money_is_an_accountless_staff_charge_and_returns_need_a_case():
    space, manager, donor = setup("sp-money", "finance.sponsors")
    sponsor = _sponsor(space, manager)
    charged = client(manager).post(url(space, f"/{sponsor.pk}/charges"), {"amount": "25000", "description": "2026"},
                                   format="json")
    assert charged.status_code == 201, charged.content
    payment = Payment.objects.get(subject_type="sponsorship", subject_id=charged.json()["id"])
    assert payment.member is None and payment.created_by == manager and payment.status == "pending"
    from apps.payments.finance_scope import PAYMENT_DOMAINS
    assert PAYMENT_DOMAINS["sponsorship"] == "donations"
    refused = client(manager).post(url(space, f"/charges/{charged.json()['id']}/return"), {}, format="json")
    assert refused.status_code == 400 and refused.json()["code"] == "refund_not_settled"


def test_the_wall_shows_public_fields_only_and_hides_archived_and_off_window_sponsors():
    space, manager, donor = setup("sp-wall", "finance.sponsors")
    shown = _sponsor(space, manager)
    hidden = _sponsor(space, manager, name="Old Sponsor", ends_on=str(timezone.localdate() - timedelta(days=1)))
    _sponsor(space, manager, name="Quiet Sponsor", show_on_wall=False)
    wall = APIClient().get(f"/api/v1/public/{space.slug}/sponsors")
    assert wall.status_code == 200
    names = [row["name"] for row in wall.json()["results"]]
    assert names == ["Acme Robotics"]
    body = wall.content.decode()
    for private in ("rita@acme.example", "Rita Contact", "+919900000000"):
        assert private not in body
    client(manager).post(url(space, f"/{shown.pk}/archive"), {}, format="json")
    assert APIClient().get(f"/api/v1/public/{space.slug}/sponsors").json()["results"] == []
    switch(space, "finance.sponsors", on=False)
    assert APIClient().get(f"/api/v1/public/{space.slug}/sponsors").status_code == 404
    assert Sponsor.objects.filter(pk=hidden.pk).exists()


def test_the_pages_section_projects_the_wall_and_renders_nothing_when_off():
    from apps.makerspaces.public_page_derived import derived_payload
    space, manager, donor = setup("sp-page", "finance.sponsors")
    _sponsor(space, manager)
    payload = derived_payload("makerspace", space, "sponsors", {"title": "Our sponsors"})
    assert payload["title"] == "Our sponsors" and payload["results"][0]["name"] == "Acme Robotics"
    assert "contact_email" not in payload["results"][0]
    switch(space, "finance.sponsors", on=False)
    assert derived_payload("makerspace", space, "sponsors", {"title": "Our sponsors"}) is None


def test_contacts_are_scoped_pii_and_updates_never_put_them_in_the_audit():
    space, manager, donor = setup("sp-pii", "finance.sponsors")
    sponsor = _sponsor(space, manager)
    client(manager).patch(url(space, f"/{sponsor.pk}"), {"contact_email": "new@acme.example"}, format="json")
    rows = AuditLog.objects.filter(action__in=("sponsor.created", "sponsor.updated"))
    assert "rita@acme.example" not in str(list(rows.values("meta"))) and "new@acme" not in str(list(rows.values("meta")))
    from apps.encryption.registry import fields_for_label
    assert {field.field_name for field in fields_for_label("payments.Sponsor")} == {
        "contact_name", "contact_email", "contact_phone"}


def test_event_sponsors_are_linked_never_copied_and_show_on_the_event_wall():
    from apps.events.models import Event, EventSponsor
    from tests.events.checkin_helpers import make_event
    space, manager, donor = setup("sp-event", "finance.sponsors")
    sponsor = _sponsor(space, manager)
    event = make_event(space, "Robot arena", listing=Event.Listing.LISTED, page_state=Event.PageState.LIVE)
    row = EventSponsor.objects.create(event=event, makerspace=space, label="Acme (arena)")
    choices = client(manager).get(url(space, "/event-sponsors"))
    assert choices.status_code == 200 and choices.json()[0]["id"] == row.pk and choices.json()[0]["linked_sponsor_id"] is None
    linked = client(manager).post(url(space, f"/{sponsor.pk}/event-links"), {"event_sponsor": row.pk}, format="json")
    assert linked.status_code == 201, linked.content
    assert EventSponsor.objects.filter(event=event).count() == 1  # linked, not duplicated
    wall = APIClient().get(f"/api/v1/public/{space.slug}/events/{event.public_token}/sponsors")
    assert wall.status_code == 200 and [card["name"] for card in wall.json()["results"]] == ["Acme Robotics"]
    other = _sponsor(space, manager, name="Rival Co")
    taken = client(manager).post(url(space, f"/{other.pk}/event-links"), {"event_sponsor": row.pk}, format="json")
    assert taken.status_code == 400 and taken.json()["code"] == "event_sponsor_linked"
    link_id = linked.json()["id"]
    assert client(manager).delete(url(space, f"/event-links/{link_id}")).status_code == 204
    assert APIClient().get(f"/api/v1/public/{space.slug}/events/{event.public_token}/sponsors").json()["results"] == []
