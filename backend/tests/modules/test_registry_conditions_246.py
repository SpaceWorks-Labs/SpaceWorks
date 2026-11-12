"""Decision 246: registry-driven on/off matrix for EVERY module and EVERY capability key.

One parametrised row per key, so a module added later is covered without editing this file:
the module answers `module_enabled` only while stored on, a capability answers
`feature_enabled` only when its own key, its parent module, its required modules and its
required features are all on, and any one missing prerequisite switches it off.
"""
import pytest

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_definitions import RETIRED_FEATURES
from apps.makerspaces.capability_eligibility import LOAN_FEATURES
from apps.makerspaces.loan_visibility import INVENTORY_ONLY_MODULES
from apps.makerspaces.module_registry import BY_KEY, MODULE_KEYS, core_module_keys, with_dependencies
from apps.makerspaces.platform import feature_enabled, module_enabled
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db

OPTIONAL_MODULES = sorted(key for key in MODULE_KEYS if not BY_KEY[key].is_core)
FEATURE_KEYS = sorted(FEATURES)


def _set(space, modules, features):
    space.enabled_modules = sorted(modules)
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_modules", "enabled_features"])
    space.refresh_from_db()
    return space


def _prerequisites(key, seen=None):
    """Every module and feature key the capability needs, transitively."""
    definition = FEATURES[key]
    modules = {m for m in (definition.parent_module, *definition.requires_modules) if m}
    features = set(definition.requires_features)
    if key in LOAN_FEATURES and key != "loans.enabled":
        # The Inventory master and its own parent module (decision 254).
        master_modules, master_features = _prerequisites("loans.enabled")
        modules |= master_modules
        features |= master_features | {"loans.enabled"}
    for feature in definition.requires_features:
        sub_modules, sub_features = _prerequisites(feature)
        modules |= sub_modules
        features |= sub_features
    return modules, features


@pytest.mark.parametrize("key", OPTIONAL_MODULES)
def test_module_is_on_only_while_stored_on_and_off_after_removal(key):
    space = make_space(f"reg-mod-{key}".replace("_", "-")[:50])
    # Inventory-only modules answer off while the Inventory master is off (decision 254).
    master = ["loans.enabled"] if key in INVENTORY_ONLY_MODULES else []
    _set(space, with_dependencies([key, "staff_admin"]) if master else with_dependencies([key]), master)
    assert module_enabled(space, key)
    _set(space, set(space.enabled_modules) - {key}, master)
    assert not module_enabled(space, key)


@pytest.mark.parametrize("key", OPTIONAL_MODULES)
def test_module_dependencies_all_exist_and_are_not_circular(key):
    definition = BY_KEY[key]
    assert all(dep in MODULE_KEYS for dep in definition.requires_modules)
    assert key not in with_dependencies(definition.requires_modules)


def test_core_modules_are_never_default_off_and_never_require_optional_modules():
    for key in core_module_keys():
        assert not BY_KEY[key].default_enabled
        assert all(BY_KEY[dep].is_core for dep in BY_KEY[key].requires_modules)


@pytest.mark.parametrize("key", FEATURE_KEYS)
def test_capability_is_on_only_with_every_prerequisite_on(key):
    modules, features = _prerequisites(key)
    space = make_space(f"reg-feat-{key}".replace("_", "-").replace(".", "-")[:50])
    _set(space, with_dependencies(modules), features | {key})
    definition = FEATURES[key]
    if definition.app_label is not None:
        pytest.skip("owning app may be tombstoned in this deployment profile")
    if key in RETIRED_FEATURES:
        # Decisions 319/218: a retired capability always reads off, whatever is stored.
        assert not feature_enabled(space, key)
        return
    assert feature_enabled(space, key), f"{key} should be on with all prerequisites"
    _set(space, with_dependencies(modules), features)
    assert not feature_enabled(space, key), "a stored-off key must read off"


@pytest.mark.parametrize("key", [k for k in FEATURE_KEYS if FEATURES[k].parent_module])
def test_capability_is_off_when_its_parent_module_is_removed(key):
    modules, features = _prerequisites(key)
    parent = FEATURES[key].parent_module
    space = make_space(f"reg-par-{key}".replace("_", "-").replace(".", "-")[:50])
    _set(space, with_dependencies(modules) - {parent}, features | {key})
    assert not feature_enabled(space, key)


@pytest.mark.parametrize("key", [k for k in FEATURE_KEYS if FEATURES[k].requires_features])
def test_capability_is_off_when_a_required_feature_is_off(key):
    modules, features = _prerequisites(key)
    space = make_space(f"reg-req-{key}".replace("_", "-").replace(".", "-")[:50])
    missing = sorted(FEATURES[key].requires_features)[0]
    _set(space, with_dependencies(modules), (features | {key}) - {missing})
    assert not feature_enabled(space, key)


@pytest.mark.parametrize("key", FEATURE_KEYS)
def test_capability_definition_references_only_registered_keys(key):
    definition = FEATURES[key]
    if definition.parent_module is not None:
        assert definition.parent_module in MODULE_KEYS
    assert all(m in MODULE_KEYS for m in definition.requires_modules)
    assert all(f in FEATURES for f in definition.requires_features)
    assert key not in definition.requires_features


def test_unknown_capability_key_reads_off_everywhere():
    space = _set(make_space("reg-unknown"), MODULE_KEYS, FEATURES)
    assert not feature_enabled(space, "nonexistent.capability")
    assert not module_enabled(space, "nonexistent_module")
