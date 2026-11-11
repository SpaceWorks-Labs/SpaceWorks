from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from apps.makerspaces.admin_capability_completion import complete_selection
from apps.makerspaces.capabilities import prune_features, validate_capabilities
from apps.makerspaces.capability_projection import feature_flags_for_servable
from apps.makerspaces.module_registry import core_module_keys, with_dependencies
from apps.makerspaces.setup_areas import features_for


SEARCH = "events.gallery_search"
GALLERY = "events.project_gallery"
HACKATHONS = "events.hackathons"


def test_unrelated_module_change_retains_the_dormant_search_default():
    modules = with_dependencies(core_module_keys() | {"events", "reports"})
    kept, dropped = prune_features([SEARCH, "events.peoples_choice"], modules)

    assert kept == [SEARCH]
    assert dropped == ["events.peoples_choice"]
    with pytest.raises(ValidationError, match=GALLERY):
        validate_capabilities(list(modules), kept)
    validate_capabilities(list(modules), kept, dormant_defaults=kept)


def test_unchanged_search_does_not_enable_the_gallery_but_activates_with_it():
    modules = with_dependencies(core_module_keys() | {"events"})
    dormant = complete_selection(modules, modules, [SEARCH], [SEARCH])
    assert dormant.features == [SEARCH]
    assert dormant.added == []
    space = SimpleNamespace(enabled_modules=dormant.modules, enabled_features=dormant.features)
    assert feature_flags_for_servable(space, [SEARCH]) == {SEARCH: False}

    enabled = complete_selection(modules, modules, [SEARCH, GALLERY], [SEARCH])
    assert {SEARCH, GALLERY, HACKATHONS} <= set(enabled.features)
    space.enabled_features = enabled.features
    assert feature_flags_for_servable(space, [SEARCH]) == {SEARCH: True}

    newly_selected = complete_selection(modules, modules, [SEARCH])
    assert {SEARCH, GALLERY, HACKATHONS} <= set(newly_selected.features)


def test_an_explicit_search_opt_out_survives_enabling_the_gallery():
    modules = with_dependencies(core_module_keys() | {"events"})
    disabled = complete_selection(modules, modules, [], [SEARCH])
    enabled = complete_selection(modules, modules, [GALLERY], disabled.features)

    assert GALLERY in enabled.features
    assert SEARCH not in enabled.features


def test_event_area_setup_stores_search_without_enabling_the_gallery():
    configured = features_for(["events"])
    assert SEARCH in configured
    assert GALLERY not in configured
