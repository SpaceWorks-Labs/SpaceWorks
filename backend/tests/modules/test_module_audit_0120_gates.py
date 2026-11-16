"""Module audit 0.12.0: route gates at the deployment (platform) level and per space.

Uses the primary-surface probes of `test_module_contract_matrix` (every optional module with a
cheap verified probe), so a probe added there is covered here too:

* a module the deployment does not ship (TOMBSTONED_APPS) is off in every space even when the
  space's stored row says on, and the console shows it locked and refuses to install it;
* a module switched off in one space refuses there and leaves another space untouched;
* switching off keeps the data and switching back on restores the surface;
* a feature switched off in one space refuses with the typed 404 and leaves another space alone.
"""

import pytest
from django.db import transaction
from django.urls import reverse

from apps.makerspaces.module_install import install_module, uninstall_module
from apps.makerspaces.module_registry import BY_KEY, core_module_keys, with_dependencies
from apps.makerspaces.platform import available_modules
from apps.separability import registry as separability
from apps.separability.tombstones import SEPARABLE_APPS
from tests.fixed_roles.helpers import staff_account
from tests.makerspaces.test_module_purge import an_event
from tests.module_helpers import disable_module
from tests.modules.test_module_contract_matrix import PROBES, _actor, _client, _space
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db

CORE = frozenset(core_module_keys())
PROBED = sorted(key for key, probe in PROBES.items() if probe is not None)
# Only an app on the separability list can be left out of a deployment.
SHIPPABLE = sorted(key for key in PROBED if BY_KEY[key].app_label in SEPARABLE_APPS)


class _Discard(Exception):
    pass


def _probe(key, space, client):
    """Call the module's probe and roll back whatever it wrote, so a probe that creates a row
    (a named queue, a join request) can run again on the same space."""
    try:
        with transaction.atomic():
            raise _Discard(PROBES[key](space, client))
    except _Discard as done:
        return done.args[0]


def _ok(response):
    return 200 <= response.status_code < 300


def _refused(response):
    return 400 <= response.status_code < 500


def ship_without(monkeypatch, app_label):
    real = separability.runtime_active
    fake = lambda label: label != app_label and real(label)  # noqa: E731
    monkeypatch.setattr(separability, "runtime_active", fake)
    monkeypatch.setattr("apps.makerspaces.capability_eligibility.runtime_active", fake)
    monkeypatch.setattr("apps.makerspaces.capability_projection.runtime_active", fake)


def test_the_audit_covers_the_modules_that_own_routes():
    assert len(PROBED) >= 20 and SHIPPABLE


# --- deployment (platform) level ----------------------------------------------------------


@pytest.mark.parametrize("key", SHIPPABLE)
def test_a_module_the_deployment_does_not_ship_is_off_in_every_space(key, monkeypatch):
    space = _space(key, "deploy", CORE | with_dependencies({key}))
    client = _client(_actor(key, "deploy"))
    ship_without(monkeypatch, BY_KEY[key].app_label)

    response = _probe(key, space, client)

    assert _refused(response), f"{key}: {response.status_code}"
    assert key not in available_modules(space)
    space.refresh_from_db()
    assert key in space.enabled_modules  # the tenant's stored choice is never rewritten


def test_the_console_locks_a_module_the_deployment_does_not_ship(monkeypatch):
    space = make_space("audit-console-lock")
    disable_module(space, "bookings")
    client = authenticated_client(staff_account(space, "audit-lock-sm", "space_manager"))
    ship_without(monkeypatch, "bookings")

    groups = client.get(reverse("admin-module-groups", args=[space.pk]))
    rows = {row["key"]: row for group in groups.data["groups"] for row in group["modules"]}
    refused = client.post(reverse("admin-module-install", args=[space.pk]), {"key": "bookings"}, format="json")

    assert groups.status_code == 200 and rows["bookings"]["available"] is False
    assert rows["bookings"].get("lock_reason", "not_shipped") == "not_shipped"
    assert refused.status_code == 400
    space.refresh_from_db()
    assert "bookings" not in space.enabled_modules


# --- per space ------------------------------------------------------------------------------


@pytest.mark.parametrize("key", PROBED)
def test_switching_a_module_off_in_one_space_leaves_another_space_untouched(key):
    modules = CORE | with_dependencies({key})
    off = _space(key, "iso-off", modules - {key})
    on = _space(key, "iso-on", modules)
    client = _client(_actor(key, "iso"))

    refused = _probe(key, off, client)
    served = _probe(key, on, client)

    assert _refused(refused), f"{key} off: {refused.status_code}"
    assert _ok(served), f"{key} on in the other space: {served.status_code} {getattr(served, 'data', '')}"


@pytest.mark.parametrize("key", PROBED)
def test_switching_a_module_off_then_on_restores_its_surface(key):
    space = _space(key, "cycle", CORE | with_dependencies({key}))
    client = _client(_actor(key, "cycle"))

    uninstall_module(space, key)
    space.refresh_from_db()
    assert _refused(_probe(key, space, client)), key
    install_module(space, key)
    space.refresh_from_db()
    response = _probe(key, space, client)
    assert _ok(response), f"{key} after reinstall: {response.status_code} {getattr(response, 'data', '')}"


def test_switching_a_module_off_keeps_its_rows_and_on_shows_them_again():
    space = _space("events", "kept", CORE | {"events"})
    client = _client(_actor("events", "kept"))
    event = an_event(space, title="Audit kept event")
    url = reverse("admin-event-list-create", args=[space.pk])

    uninstall_module(space, "events")
    assert client.get(url).status_code == 404
    assert type(event).objects.filter(pk=event.pk).exists()
    install_module(space, "events")
    response = client.get(url)
    assert response.status_code == 200 and "Audit kept event" in str(response.data)


# --- features -------------------------------------------------------------------------------


def _without_feature(slug, key):
    space = make_space(slug)
    space.enabled_features = [feature for feature in space.enabled_features if feature != key]
    space.save(update_fields=["enabled_features"])
    return space


def test_a_feature_off_in_one_space_is_a_typed_404_there_and_nowhere_else():
    off = _without_feature("audit-invites-off", "staff.invitations")
    on = make_space("audit-invites-on")
    for space, expected in ((off, 404), (on, 200)):
        manager = staff_account(space, f"{space.slug}-sm", "space_manager")
        response = authenticated_client(manager).get(reverse("admin-staff-invitations", kwargs={"makerspace_id": space.pk}))
        assert response.status_code == expected, (space.slug, response.status_code)
        if expected == 404:
            assert response.data["code"] == "feature_disabled" and response.data["feature"] == "staff.invitations"


def test_native_push_registration_follows_the_spaces_switch(settings):
    from apps.integrations.models import PushDevice
    from tests.test_native_push import device_client, push_member

    settings.PUSH_TOKEN_HMAC_KEY = "h" * 64
    payload = {"token": "a" * 64, "provider": "apns", "environment": "development"}
    off = _without_feature("audit-push-off", "mobile.push")
    on = make_space("audit-push-on")

    refused = device_client(push_member("audit-push-off-user", off), off)[0].post(
        "/api/v1/integrations/push/devices", payload, format="json")
    created = device_client(push_member("audit-push-on-user", on), on)[0].post(
        "/api/v1/integrations/push/devices", payload, format="json")

    assert refused.status_code == 404
    assert refused.data["code"] == "feature_disabled" and refused.data["feature"] == "mobile.push"
    assert not PushDevice.objects.filter(makerspace=off).exists()
    assert created.status_code == 201


def test_the_console_names_feature_switches_the_deployment_cannot_turn_on(monkeypatch):
    # Decision 329 (c): a feature whose own app is not shipped carries `lock_reason` `not_shipped`.
    space = make_space("audit-feature-locks")
    client = authenticated_client(staff_account(space, "audit-feature-locks-sm", "space_manager"))
    url = reverse("admin-module-groups", args=[space.pk])

    shipped = client.get(url)
    assert shipped.status_code == 200 and shipped.data["feature_locks"] == {}

    ship_without(monkeypatch, "maintenance")
    locks = client.get(url).data["feature_locks"]
    assert locks["machines.maintenance"] == "not_shipped"
    assert "machines.sessions" not in locks and "machines.certifications" not in locks
