import pytest

from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def endpoint(world):
    return f"/api/v1/integrations/makerspace/{world.space.pk}/personal/preferences"


def selection(response, category):
    assert response.status_code == 200, response.data
    return next(row for row in response.data["preferences"] if row["category"] == category)


@pytest.mark.parametrize("saved", [False, True])
def test_unrelated_save_preserves_hidden_category_then_module_defaults(world, monkeypatch, saved):
    enabled = {"hardware_requests"}
    monkeypatch.setattr("apps.integrations.notification_availability.available_channels",
                        lambda _space, category: ["email", "in_app"] if category in enabled else [])
    if saved:
        original = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
            category="events", channels=[], email_fallback=False)
    client = world.client(world.owner)
    assert selection(client.get(endpoint(world)), "events")["available_channels"] == []
    response = client.put(endpoint(world), {"preferences": [
        {"category": "hardware_requests", "channels": ["in_app"], "email_fallback": False},
    ]}, format="json")
    assert response.status_code == 200, response.data
    rows = NotificationPreference.objects.filter(makerspace=world.space, user=world.owner, category="events")
    if saved:
        assert rows.get().pk == original.pk
    else:
        assert not rows.exists()
    enabled.add("events")
    event = selection(client.get(endpoint(world)), "events")
    assert event["channels"] == ([] if saved else ["email", "in_app"])
    assert event["email_fallback"] is (not saved)


def test_empty_request_preserves_rows_and_explicit_empty_selection_is_still_an_opt_out(world, monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_availability.available_channels", lambda *_: ["in_app"])
    client = world.client(world.owner)
    data = {"category": "events", "channels": [], "email_fallback": False}
    assert client.put(endpoint(world), {"preferences": [data]}, format="json").status_code == 200
    response = client.put(endpoint(world), {"preferences": []}, format="json")
    assert selection(response, "events")["channels"] == []
    assert NotificationPreference.objects.filter(makerspace=world.space, user=world.owner).count() == 1


def test_supplied_category_replaces_its_row_without_touching_other_users(world, monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_availability.available_channels", lambda *_: ["in_app"])
    other = NotificationPreference.objects.create(makerspace=world.space, user=world.other,
        category="events", channels=["email"], email_fallback=True)
    own = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category="events", channels=["email"], email_fallback=True)
    response = world.client(world.owner).put(endpoint(world), {"preferences": [
        {"category": "events", "channels": ["in_app"], "email_fallback": False},
    ]}, format="json")
    assert response.status_code == 200, response.data
    own.refresh_from_db()
    other.refresh_from_db()
    assert own.channels == ["in_app"] and not own.email_fallback
    assert other.channels == ["email"] and other.email_fallback


def test_unavailable_selection_still_rejects_without_erasing_preferences(world, monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_availability.available_channels", lambda *_: [])
    original = NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category="events", channels=["email"], email_fallback=True)
    response = world.client(world.owner).put(endpoint(world), {"preferences": [
        {"category": "events", "channels": ["in_app"], "email_fallback": False},
    ]}, format="json")
    assert response.status_code == 400
    original.refresh_from_db()
    assert original.channels == ["email"] and original.email_fallback
