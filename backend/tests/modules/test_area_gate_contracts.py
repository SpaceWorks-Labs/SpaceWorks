"""Fast gate contracts for every area and live capability, without URL crawls.

These exercise the shared DRF boundary and configuration dependency evaluator using
unsaved Django models. Domain workflows and persisted-row retention remain covered
by the area's API/service suites; this is deliberately not a substitute for them.
"""
from copy import deepcopy

import pytest

from apps.makerspaces.capability_definitions import FEATURES, RETIRED_FEATURES
from apps.makerspaces.capability_validation import feature_required_modules
from apps.makerspaces.guards import SurfaceOff, require_feature, require_module
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import BY_KEY, MODULE_KEYS, core_module_keys, with_dependencies

CORE = core_module_keys()
LIVE_FEATURES = sorted(FEATURES.keys() - RETIRED_FEATURES)
OPTIONAL = sorted(MODULE_KEYS - CORE)
MODULE_EDGES = sorted((key, parent) for key, definition in BY_KEY.items() for parent in definition.requires_modules)
FEATURE_MODULE_EDGES = sorted((key, parent) for key in LIVE_FEATURES for parent in feature_required_modules(key))
FEATURE_EDGES = sorted((key, parent) for key in LIVE_FEATURES for parent in FEATURES[key].requires_features)


def _space(modules=MODULE_KEYS):
    return Makerspace(name="Area gate space", slug="area-gate", enabled_modules=sorted(modules),
                      enabled_features=list(LIVE_FEATURES), branding_config={"display_name": "Retained name"})


def _assert_off(gate, space, key, kind):
    with pytest.raises(SurfaceOff) as caught:
        gate(space, key)
    assert caught.value.status_code == 404
    assert str(caught.value.detail["code"]) == f"{kind}_disabled"
    assert str(caught.value.detail[kind]) == key


@pytest.mark.parametrize("module_key", OPTIONAL)
def test_area_module_own_key_off_then_on_restores_gate_without_mutating_configuration(module_key):
    # Only its declared prerequisites are present: unrelated modules must not be needed.
    enabled = CORE | with_dependencies({module_key})
    space = _space(enabled)
    before = deepcopy((space.enabled_modules, space.enabled_features, space.branding_config))
    assert require_module(space, module_key) is space

    space.enabled_modules.remove(module_key)
    _assert_off(require_module, space, module_key, "module")
    space.enabled_modules = list(before[0])

    assert require_module(space, module_key) is space
    assert (space.enabled_modules, space.enabled_features, space.branding_config) == before


@pytest.mark.parametrize("key", LIVE_FEATURES)
def test_area_capability_off_then_on_restores_gate_and_keeps_configuration(key):
    space = _space()
    before = deepcopy((space.enabled_modules, space.enabled_features, space.branding_config))
    assert require_feature(space, key) is space

    space.enabled_features.remove(key)
    _assert_off(require_feature, space, key, "feature")
    space.enabled_features = list(before[1])

    assert require_feature(space, key) is space
    assert (space.enabled_modules, space.enabled_features, space.branding_config) == before


@pytest.mark.parametrize("key,parent", FEATURE_MODULE_EDGES)
def test_area_capability_refuses_when_a_connected_module_is_off_and_restores_with_it(key, parent):
    space = _space()
    before = deepcopy(space.enabled_features)
    assert require_feature(space, key) is space

    space.enabled_modules.remove(parent)
    _assert_off(require_feature, space, key, "feature")
    assert space.enabled_features == before  # Stored child selection is retained, but dormant.
    space.enabled_modules.append(parent)

    assert require_feature(space, key) is space
    assert space.enabled_features == before


@pytest.mark.parametrize("key,parent", FEATURE_EDGES)
def test_area_capability_refuses_when_a_connected_capability_is_off_and_restores_with_it(key, parent):
    space = _space()
    assert require_feature(space, key) is space

    space.enabled_features.remove(parent)
    _assert_off(require_feature, space, key, "feature")
    assert key in space.enabled_features
    space.enabled_features.append(parent)

    assert require_feature(space, key) is space


@pytest.mark.parametrize("module_key", OPTIONAL)
def test_area_module_switch_is_local_to_its_tenant(module_key):
    first, other = _space(), _space()
    first.enabled_modules.remove(module_key)

    _assert_off(require_module, first, module_key, "module")
    assert require_module(other, module_key) is other
    assert other.enabled_modules == sorted(MODULE_KEYS)


@pytest.mark.parametrize("child,parent", MODULE_EDGES)
def test_area_module_dependency_validation_keeps_the_connected_modules_explicit(child, parent):
    from django.core.exceptions import ValidationError
    from apps.makerspaces.capability_validation import validate_capabilities

    enabled = CORE | with_dependencies({child})
    assert validate_capabilities(sorted(enabled), [])[0] == sorted(enabled)
    with pytest.raises(ValidationError) as caught:
        validate_capabilities(sorted(enabled - {parent}), [])
    assert set(caught.value.message_dict) == {"enabled_modules"}
    assert caught.value.message_dict["enabled_modules"] == [
        f"{BY_KEY[child].label} requires {BY_KEY[parent].label.lower()} to be enabled."
    ]
    assert validate_capabilities(sorted(enabled), [])[0] == sorted(enabled)


@pytest.mark.parametrize("key", sorted(RETIRED_FEATURES))
def test_retired_capabilities_stay_refused_even_when_stored_on(key):
    space = _space()
    space.enabled_features.append(key)
    _assert_off(require_feature, space, key, "feature")
    assert key in space.enabled_features


@pytest.mark.parametrize("module_key", sorted(CORE))
def test_core_area_modules_refuse_uninstallation_without_touching_configuration(module_key):
    from apps.makerspaces.module_install import ModuleInstallError, uninstall_module

    space = _space()
    before = deepcopy(space.enabled_modules)
    with pytest.raises(ModuleInstallError) as caught:
        uninstall_module(space, module_key)
    assert str(caught.value) == f"{module_key} is a core module and cannot be uninstalled."
    assert space.enabled_modules == before
