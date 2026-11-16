"""Arch review 7: the modules route publishes each feature's canonical prerequisites.

The console (frontend/src/features/staff/modules/modulePlans.ts) plans transitive enabling and
dependent removal from `feature_requirements`. These tests pin the payload to the capability
registry and prove that the plans it implies are the ones `validate_capabilities` accepts.
"""
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.admin_api.views_modules import feature_requirements
from apps.makerspaces.capability_definitions import FEATURE_DEFINITIONS, FEATURES, RETIRED_FEATURES
from apps.makerspaces.capability_validation import (
    feature_required_modules, required_feature_closure, validate_capabilities,
)
from apps.makerspaces.module_registry import core_module_keys, with_dependencies
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

ACCESS = "machines.integrations.access"


def test_payload_mirrors_the_registry_for_every_switchable_feature():
    payload = feature_requirements()
    expected = {definition.key for definition in FEATURE_DEFINITIONS if definition.key not in RETIRED_FEATURES}
    assert set(payload) == expected
    for key, entry in payload.items():
        assert entry["modules"] == list(feature_required_modules(key))
        assert entry["features"] == list(FEATURES[key].requires_features)
        assert FEATURES[key].parent_module is None or FEATURES[key].parent_module in entry["modules"]
    assert not set(payload) & RETIRED_FEATURES


def test_a_feature_with_non_parent_requirements_is_described():
    entry = feature_requirements()[ACCESS]
    definition = FEATURES[ACCESS]
    assert definition.parent_module in entry["modules"]
    assert set(definition.requires_modules) <= set(entry["modules"])
    assert entry["features"] == list(definition.requires_features)
    assert entry["features"], "the canonical example must require another feature"


def _closure_plan(key):
    """What the console sends: every transitive module and feature, then the feature itself."""
    payload = feature_requirements()
    features = required_feature_closure({key})
    modules = {module for feature in features for module in payload[feature]["modules"]}
    return sorted(with_dependencies(modules | set(core_module_keys()))), sorted(features)


@pytest.mark.parametrize("key", sorted(
    definition.key for definition in FEATURE_DEFINITIONS
    if definition.key not in RETIRED_FEATURES and (definition.requires_features or definition.requires_modules)))
def test_switching_on_with_every_prerequisite_is_valid(key):
    modules, features = _closure_plan(key)
    validate_capabilities(modules, features)


def test_parent_only_plans_are_refused_where_the_registry_needs_more():
    # The defect the old console had: only the parent module and the feature itself.
    parent = FEATURES[ACCESS].parent_module
    with pytest.raises(ValidationError):
        validate_capabilities(sorted(with_dependencies({parent} | set(core_module_keys()))), [ACCESS])


def test_dropping_a_prerequisite_without_its_dependents_is_refused_and_with_them_is_valid():
    modules, features = _closure_plan(ACCESS)
    needed = FEATURES[ACCESS].requires_features[0]
    with pytest.raises(ValidationError):
        validate_capabilities(modules, [key for key in features if key != needed])
    validate_capabilities(modules, [key for key in features if key not in (needed, ACCESS)])


@pytest.mark.django_db
def test_the_modules_route_returns_feature_requirements_to_space_staff():
    space = make_space("feature-requirements")
    client = authenticated_client(staff_account(space, "feature-requirements-sm", "space_manager"))
    response = client.get(reverse("admin-module-groups", args=[space.pk]))
    assert response.status_code == 200
    assert response.data["feature_requirements"] == feature_requirements()


@pytest.mark.django_db
def test_the_modules_route_still_refuses_anonymous_callers():
    space = make_space("feature-requirements-anon")
    from rest_framework.test import APIClient
    assert APIClient().get(reverse("admin-module-groups", args=[space.pk])).status_code in (401, 403)
