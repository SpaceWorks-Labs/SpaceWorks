"""Configuration eligibility and fresh batched reads, independent of HTTP gates."""
import pytest

from apps.makerspaces import module_registry as registry
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_definitions import RETIRED_FEATURES
from apps.makerspaces.capability_eligibility import (
    configuration_feature_enabled, feature_enabled_servable_ids, unavailable_features,
)
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import request_scope


def configured():
    return Makerspace(name="Eligibility", slug="cx6-eligibility",
                      enabled_modules=sorted(registry.MODULE_KEYS), enabled_features=sorted(FEATURES))


@pytest.mark.parametrize("key", sorted(set(FEATURES) - RETIRED_FEATURES))
def test_each_live_capability_switch_and_each_declared_dependency(key):
    space = configured()
    assert configuration_feature_enabled(space, key) is True
    original_features = list(space.enabled_features)
    original_modules = list(space.enabled_modules)
    space.enabled_features.remove(key)
    assert configuration_feature_enabled(space, key) is False
    space.enabled_features = original_features.copy()
    assert configuration_feature_enabled(space, key) is True
    definition = FEATURES[key]
    for dependency in {definition.parent_module, *definition.requires_modules} - {None}:
        space.enabled_modules = [module for module in original_modules if module != dependency]
        assert configuration_feature_enabled(space, key) is False
        space.enabled_modules = original_modules.copy()
        assert configuration_feature_enabled(space, key) is True
    for dependency in definition.requires_features:
        space.enabled_features = [feature for feature in original_features if feature != dependency]
        assert configuration_feature_enabled(space, key) is False
        space.enabled_features = original_features.copy()
        assert configuration_feature_enabled(space, key) is True


@pytest.mark.parametrize("key", sorted(RETIRED_FEATURES) + ["unknown.capability"])
def test_retired_and_unknown_capabilities_never_read_on(key):
    space = configured()
    space.enabled_features.append(key)
    assert configuration_feature_enabled(space, key) is False


def test_unknown_configuration_is_not_misreported_as_an_unavailable_app():
    assert unavailable_features(["unknown.capability", *RETIRED_FEATURES]) == sorted(RETIRED_FEATURES)
    assert registry.module_available("unknown-legacy-module") is True
    assert registry.is_frontend_exposed("unknown-legacy-module") is True
    assert registry.group_for("unknown-legacy-module") is None
    assert registry.group_is_always_on("unknown-group") is False
    assert registry.group_module_keys("unknown-group") == ()
    assert registry.with_dependencies(["unknown-legacy-module", "unknown-legacy-module"]) == {"unknown-legacy-module"}
    assert registry.dependents_of("unknown-legacy-module", registry.MODULE_KEYS) == []


@pytest.mark.django_db
def test_batched_eligibility_reads_current_tenant_state_without_mutating_stored_features():
    on = Makerspace.objects.create(name="On", slug="cx6-on", enabled_modules=["membership", "member_accounts"],
                                   enabled_features=["membership.self_export"])
    off = Makerspace.objects.create(name="Off", slug="cx6-off", enabled_modules=["member_accounts"],
                                    enabled_features=["membership.self_export"])
    paused = Makerspace.objects.create(name="Paused", slug="cx6-paused", lifecycle_state="suspended",
        enabled_modules=["membership", "member_accounts"], enabled_features=["membership.self_export"])
    ids = [on.pk, off.pk, paused.pk, 987654321]
    with request_scope():
        assert feature_enabled_servable_ids(ids, "membership.self_export") == {on.pk}
        assert feature_enabled_servable_ids([], "membership.self_export") == set()
        Makerspace.objects.filter(pk=off.pk).update(enabled_modules=["membership", "member_accounts"])
        assert feature_enabled_servable_ids(ids, "membership.self_export") == {on.pk, off.pk}
        Makerspace.objects.filter(pk=on.pk).update(enabled_features=[])
        assert feature_enabled_servable_ids(ids, "membership.self_export") == {off.pk}
    off.refresh_from_db()
    assert off.enabled_features == ["membership.self_export"]


def test_registry_results_do_not_share_mutable_defaults():
    defaults = registry.default_enabled_module_keys()
    before = list(defaults)
    defaults.clear()
    assert registry.default_enabled_module_keys() == before
    workflows = registry.module_workflows()
    before_workflows = {key: value.copy() for key, value in workflows.items()}
    for value in workflows.values():
        value.clear()
    assert registry.module_workflows() == before_workflows
