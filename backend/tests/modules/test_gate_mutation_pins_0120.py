"""Mutation pins (decision 457) for the module/feature gate helpers and the servability admission."""
from unittest.mock import Mock

import pytest

from apps.makerspaces import module_registry, servability
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled, module_enabled
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
State = Makerspace.LifecycleState


def _space(slug, features=(), modules=()):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.enabled_modules = sorted(set(space.enabled_modules or []) | set(modules))
    space.save(update_fields=["enabled_features", "enabled_modules"])
    return space


def test_feature_enabled_follows_the_stored_switch_for_a_live_space():
    space = _space("gmp-feature", features=["loans.enabled", "inventory.kiosk"], modules=["public_inventory"])
    assert feature_enabled(space, "loans.enabled") is True
    assert feature_enabled(space, "inventory.kiosk") is True
    assert feature_enabled(space, "inventory.expected_back") is False
    assert feature_enabled(space, "no.such.feature") is False


@pytest.mark.parametrize("state, expected", [
    (State.ACTIVE, True), (State.SUSPENDED, True), (State.IMPORTING, False), (State.ABORTED, False),
])
def test_feature_and_module_answers_fail_closed_only_for_the_new_lifecycle_states(state, expected):
    space = _space(f"gmp-state-{state}", features=["loans.enabled"], modules=["notifications"])
    Makerspace.objects.filter(pk=space.pk).update(lifecycle_state=state)
    space.refresh_from_db()
    assert feature_enabled(space, "loans.enabled") is expected
    assert module_enabled(space, "notifications") is expected


def test_an_archived_space_still_answers_capability_questions_false_only_by_state():
    from django.utils import timezone

    space = _space("gmp-archived", features=["loans.enabled"])
    Makerspace.objects.filter(pk=space.pk).update(archived_at=timezone.now())
    space.refresh_from_db()
    # Capability, not liveness: archival is left to the archived checks (see feature_enabled).
    assert feature_enabled(space, "loans.enabled") is True


def test_superadmin_admission_is_scoped_to_the_request_and_defaults_closed():
    assert servability.superadmin_admitted() is False
    assert servability.servable_states() == (State.ACTIVE,)
    with servability.request_scope():
        assert servability.superadmin_admitted() is False
        servability._superadmin_admitted.set(True)
        assert servability.superadmin_admitted() is True
        assert servability.servable_states() == (State.ACTIVE, State.SUSPENDED)
    assert servability.superadmin_admitted() is False


def test_a_suspended_space_is_servable_only_for_the_admitted_superadmin_but_always_for_capability():
    space = _space("gmp-suspended")
    Makerspace.objects.filter(pk=space.pk).update(lifecycle_state=State.SUSPENDED)
    space.refresh_from_db()
    assert servability.is_servable(space) is False
    assert servability.is_servable(space, allow_archived=True) is True
    with servability.request_scope():
        servability._superadmin_admitted.set(True)
        assert servability.is_servable(space) is True


def test_the_module_registry_validates_itself_with_its_own_tables(monkeypatch):
    spy = Mock()
    monkeypatch.setattr(module_registry, "validate_registry", spy)
    module_registry._validate_registry()
    spy.assert_called_once()
    kwargs = spy.call_args.kwargs
    assert set(kwargs) == {"MODULES", "BY_KEY", "GROUPS", "GROUPS_BY_KEY", "GROUP_KEYS", "group_module_keys"}
    assert kwargs["MODULES"] is module_registry.MODULES and kwargs["BY_KEY"] is module_registry.BY_KEY


def test_the_bootstrap_payload_flags_geofence_and_donations_only_when_both_gates_are_on(monkeypatch):
    from apps.makerspaces import platform

    space = _space("gmp-bootstrap", features=["presence.geofence"])
    Makerspace.objects.filter(pk=space.pk).update(
        geofence_enabled=True, geofence_latitude=0, geofence_longitude=0, geofence_radius_m=100)
    space.refresh_from_db()
    monkeypatch.setattr(platform, "runtime_active", lambda app: True)
    monkeypatch.setattr("apps.payments.donations.nonprofit.donate_entry_enabled", lambda s: True)
    on = platform.bootstrap_payload(space)["makerspace"]
    assert on["geofence_enabled"] is True and on["donate_enabled"] is True

    monkeypatch.setattr(platform, "runtime_active", lambda app: False)
    monkeypatch.setattr("apps.payments.donations.nonprofit.donate_entry_enabled", lambda s: False)
    off = platform.bootstrap_payload(space)["makerspace"]
    assert "geofence_enabled" not in off and "donate_enabled" not in off
