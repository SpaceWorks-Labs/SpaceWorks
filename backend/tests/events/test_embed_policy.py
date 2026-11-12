"""L1 G4: the framable event card and its per-space allow-list (default off)."""

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import EventEmbedPolicy
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)
ORIGIN = "https://partner.example"


def fixture(*, feature=True):
    space = event_space("embedding")
    if feature:
        space.enabled_features += ["events.website", "events.embed"]
        space.save(update_fields=["enabled_features"])
    return space, make_staff(space), open_event(space, location="Main hall")


def policy_url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/events/embed-policy/"


def card(space, event):
    return APIClient().get(f"/embed/{space.slug}/{event.public_token}/")


def test_default_off_until_the_policy_is_enabled_with_an_origin():
    space, staff, event = fixture()
    read = client_for(staff).get(policy_url(space)).data
    assert (read["enabled"], read["allowed_origins"], read["embed_path"]) == (False, [], f"/embed/{space.slug}/")
    assert card(space, event).status_code == 404
    saved = client_for(staff).put(policy_url(space), {"enabled": True, "allowed_origins": [ORIGIN]}, format="json")
    assert saved.status_code == 200
    response = card(space, event)
    assert response.status_code == 200
    assert response["Content-Security-Policy"].endswith(f"frame-ancestors {ORIGIN}")
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    html = response.content.decode()
    assert 'target="_blank"' in html and "<form" not in html and event.title in html
    row = AuditLog.objects.get(action="event.embed_policy_updated")
    assert row.meta["origins_added"] == [ORIGIN] and row.meta["via"] == "space_manager"


def test_origins_must_be_exact_https():
    space, staff, _event = fixture()
    for bad in (["http://partner.example"], ["https://*.partner.example"], ["https://partner.example/path"]):
        response = client_for(staff).put(policy_url(space), {"enabled": True, "allowed_origins": bad}, format="json")
        assert response.status_code == 400, bad


def test_capability_off_hides_the_card_and_the_settings_but_keeps_the_policy():
    space, staff, event = fixture()
    client_for(staff).put(policy_url(space), {"enabled": True, "allowed_origins": [ORIGIN]}, format="json")
    space.enabled_features.remove("events.embed")
    space.save(update_fields=["enabled_features"])
    assert card(space, event).status_code == 404
    assert client_for(staff).get(policy_url(space)).status_code == 404
    assert EventEmbedPolicy.objects.get(makerspace=space).allowed_origins == [ORIGIN]


def test_card_follows_the_public_gate_and_never_carries_the_join_link():
    space, staff, event = fixture()
    space.enabled_features += ["events.online_delivery"]
    space.save(update_fields=["enabled_features"])
    client_for(staff).put(policy_url(space), {"enabled": True, "allowed_origins": [ORIGIN]}, format="json")
    client_for(staff).patch(f"/api/v1/admin/events/{event.pk}/",
                            {"delivery_mode": "online", "join_url": "https://meet.example.test/x"}, format="json")
    html = card(space, event).content.decode()
    assert "meet.example.test" not in html and "Online" in html and "Main hall" not in html
    event.page_state = "offline"
    event.save(update_fields=["page_state"])
    assert card(space, event).status_code == 404


def test_event_manager_needs_the_events_settings_grant_to_change_the_policy():
    from apps.makerspaces.settings_authority_writes import set_grants
    from tests.accounts.account_factories import make_staff as staff_with_role
    space, staff, _event = fixture()
    manager = staff_with_role(space, username="evm-embed", role_slug="event_manager",
                              email="evm-embed@example.test", access_status="active")
    body = {"enabled": True, "allowed_origins": [ORIGIN]}
    assert client_for(manager).get(policy_url(space)).status_code == 200
    refused = client_for(manager).put(policy_url(space), body, format="json")
    assert refused.status_code == 403 and refused.data["code"] == "setting_not_delegated"
    set_grants(staff, space, "events", [manager.pk])
    assert client_for(manager).put(policy_url(space), body, format="json").status_code == 200
