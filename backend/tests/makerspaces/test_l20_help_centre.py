"""Lane L20: the help centre switch (`platform.help_centre`, #69, #128 C-31).

Local test (never committed). The guide itself is frontend content; the backend owns only
the switch, its default, the setup-area bundle, the backfill and the reserved route.
"""

import importlib
import re
from pathlib import Path

import pytest
from django.apps import apps

from apps.makerspaces.capabilities import FEATURES, default_enabled_features, validate_capabilities
from apps.makerspaces.module_registry import core_module_keys
from apps.makerspaces.platform import bootstrap_payload
from apps.makerspaces.public_profile_reserved import RESERVED_SEGMENTS
from apps.makerspaces.setup_areas import AREAS, features_for
from tests.return_helpers import make_space

KEY = "platform.help_centre"


def test_switch_is_standalone_default_on_and_frontend_exposed():
    definition = FEATURES[KEY]
    assert definition.parent_module is None
    assert definition.requires_modules == () and definition.requires_features == ()
    assert definition.default_enabled and definition.frontend_exposed
    assert KEY in default_enabled_features()
    validate_capabilities(sorted(core_module_keys()), [KEY])


@pytest.mark.parametrize("area", list(AREAS))
def test_every_setup_area_switches_it_on(area):
    assert KEY in features_for({area})


def test_frontend_mirror_lists_it_as_standalone():
    source = (Path(__file__).resolve().parents[3] / "frontend/src/lib/features.ts").read_text(encoding="utf-8")
    assert re.search(r'key: "platform\.help_centre", parent_module: null, label: "Help centre"', source)


def test_help_is_a_reserved_route_segment():
    assert "help" in RESERVED_SEGMENTS


@pytest.mark.django_db
def test_bootstrap_payload_carries_the_switch_both_ways():
    space = make_space("l20-help-on")
    assert KEY in space.enabled_features
    assert KEY in bootstrap_payload(space)["features"]
    space.enabled_features = [key for key in space.enabled_features if key != KEY]
    space.save(update_fields=["enabled_features"])
    assert KEY not in bootstrap_payload(space)["features"]


@pytest.mark.django_db
def test_backfill_adds_the_switch_only_where_missing_and_reverses():
    migration = importlib.import_module("apps.makerspaces.migrations.0123_help_centre_default_on")
    missing, present = make_space("l20-missing"), make_space("l20-present")
    missing.enabled_features = [key for key in missing.enabled_features if key != KEY]
    missing.save(update_fields=["enabled_features"])
    before = list(present.enabled_features)
    migration.enable(apps, None)
    missing.refresh_from_db(), present.refresh_from_db()
    assert KEY in missing.enabled_features
    assert present.enabled_features == before
    assert len(missing.enabled_features) == len(set(missing.enabled_features))
    migration.disable(apps, None)
    missing.refresh_from_db(), present.refresh_from_db()
    assert KEY not in missing.enabled_features and KEY not in present.enabled_features


def test_modules_doc_describes_the_switch():
    text = (Path(__file__).resolve().parents[3] / "docs/MODULES.md").read_text(encoding="utf-8")
    assert "`platform.help_centre`" in text and "## The help centre (`platform.help_centre`)" in text
