"""Module audit 0.12.0: registry-level guarantees for EVERY module key and feature key.

Iterates the live registries, so a key added later is covered without editing this file:
the frontend mirrors agree, every switch is documented, a child cannot be on while its
parent (module, required feature, Inventory master or deployment app) is off, module
dependencies hold, and the defaults are the documented ones.
"""

import pathlib
import re
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from apps.makerspaces.capabilities import FEATURES, validate_capabilities
from apps.makerspaces.capability_definitions import RETIRED_FEATURES
from apps.makerspaces.capability_eligibility import configuration_feature_enabled, unavailable_features
from apps.makerspaces.capability_validation import feature_required_modules, required_feature_closure
from apps.makerspaces.loan_visibility import LOAN_FEATURES
from apps.makerspaces.module_registry import (
    BY_KEY, MODULE_KEYS, core_module_keys, default_enabled_module_keys, with_dependencies,
)
from apps.separability import registry as separability

ROOT = pathlib.Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend" / "src"
DOCS = ROOT / "docs"
CORE = frozenset(core_module_keys())
LIVE = sorted(set(FEATURES) - RETIRED_FEATURES)
EVERYTHING = SimpleNamespace(enabled_modules=sorted(MODULE_KEYS), enabled_features=LIVE)


def _ts_strings(path, after):
    text = (FRONTEND / path).read_text(encoding="utf-8")
    return text.split(after, 1)[1]


def ship_without(monkeypatch, app_label):
    """Simulate a deployment that does not ship `app_label` (TOMBSTONED_APPS) for the gates."""
    real = separability.runtime_active
    fake = lambda label: label != app_label and real(label)  # noqa: E731
    monkeypatch.setattr(separability, "runtime_active", fake)
    monkeypatch.setattr("apps.makerspaces.capability_eligibility.runtime_active", fake)
    monkeypatch.setattr("apps.makerspaces.capability_projection.runtime_active", fake)


def _closure_modules(key):
    modules = set()
    for feature in required_feature_closure({key}):
        modules |= set(feature_required_modules(feature))
    return with_dependencies(modules) | CORE


# --- the frontend mirrors -----------------------------------------------------------------


def test_frontend_module_names_cover_exactly_the_registry():
    block = _ts_strings("lib/moduleLabels.ts", "const MODULE_NAMES").split("});", 1)[0]
    assert set(re.findall(r"(\w+): t`", block)) == set(MODULE_KEYS)


def test_frontend_retired_module_aliases_match_the_backend():
    # Decision 340b: `printing` reads as machine_service on both sides, and neither lists it as a module.
    from apps.makerspaces.module_aliases import RETIRED_MODULE_ALIASES

    block = _ts_strings("lib/retiredModules.ts", "RETIRED_MODULE_ALIASES =").split("}", 1)[0]
    assert dict(re.findall(r'(\w+): "(\w+)"', block)) == RETIRED_MODULE_ALIASES
    assert not set(RETIRED_MODULE_ALIASES) & set(MODULE_KEYS)


def test_frontend_retired_switches_match_the_backend():
    block = _ts_strings("lib/retiredFeatures.ts", "RETIRED_FEATURES")
    assert set(re.findall(r'"([a-z_.]+)"', block)) == set(RETIRED_FEATURES)


def test_frontend_inventory_children_match_the_backend():
    block = _ts_strings("lib/featureGates.ts", "INVENTORY_CHILD_FEATURES").split("]);", 1)[0]
    assert set(re.findall(r'"([a-z_.]+)"', block)) == set(LOAN_FEATURES)


# --- documentation ------------------------------------------------------------------------


def test_the_off_reference_states_the_registry_counts():
    text = (DOCS / "MODULES-OFF.md").read_text(encoding="utf-8")
    counts = re.search(r"(\d+) module keys and (\d+) feature keys", text)
    assert counts and (int(counts.group(1)), int(counts.group(2))) == (len(MODULE_KEYS), len(FEATURES))


@pytest.mark.parametrize("key", sorted(FEATURES))
def test_every_feature_is_documented(key):
    off = (DOCS / "MODULES-OFF.md").read_text(encoding="utf-8")
    modules = (DOCS / "MODULES.md").read_text(encoding="utf-8")
    assert re.search(rf"^\| `{re.escape(key)}` \|", off, re.M), f"docs/MODULES-OFF.md has no row for {key}"
    assert f"`{key}`" in modules, f"docs/MODULES.md never names {key}"


# --- parent / child and dependencies -------------------------------------------------------


GATED = [key for key in LIVE
         if set(feature_required_modules(key)) - CORE or FEATURES[key].requires_features]


@pytest.mark.parametrize("key", GATED)
def test_a_feature_cannot_be_saved_on_without_its_parent_and_requirements(key):
    with pytest.raises(ValidationError):
        validate_capabilities(sorted(CORE), [key])
    closure = sorted(required_feature_closure({key}))
    validate_capabilities(sorted(_closure_modules(key)), closure)


@pytest.mark.parametrize("key", LIVE)
def test_a_parent_switched_off_turns_every_child_off(key):
    assert configuration_feature_enabled(EVERYTHING, key), f"{key} should be on with everything on"
    for module in _closure_modules(key) - CORE:
        modules = [m for m in EVERYTHING.enabled_modules if m != module]
        off = SimpleNamespace(enabled_modules=modules, enabled_features=LIVE)
        if module in {m for f in required_feature_closure({key}) for m in feature_required_modules(f)}:
            assert not configuration_feature_enabled(off, key), f"{key} stays on without module {module}"
    for required in required_feature_closure({key}) - {key}:
        off = SimpleNamespace(enabled_modules=EVERYTHING.enabled_modules,
                              enabled_features=[f for f in LIVE if f != required])
        assert not configuration_feature_enabled(off, key), f"{key} stays on without feature {required}"
    if key in LOAN_FEATURES and key != "loans.enabled":
        off = SimpleNamespace(enabled_modules=EVERYTHING.enabled_modules,
                              enabled_features=[f for f in LIVE if f != "loans.enabled"])
        assert not configuration_feature_enabled(off, key), f"{key} ignores the Inventory master switch"


@pytest.mark.parametrize("key", sorted(RETIRED_FEATURES))
def test_a_retired_switch_reads_off_however_it_is_stored(key):
    stored = SimpleNamespace(enabled_modules=sorted(MODULE_KEYS), enabled_features=sorted(FEATURES))
    assert not configuration_feature_enabled(stored, key)


@pytest.mark.parametrize("key", sorted(k for k, d in BY_KEY.items() if d.requires_modules))
def test_a_module_cannot_be_saved_on_without_the_modules_it_requires(key):
    with pytest.raises(ValidationError):
        validate_capabilities(sorted(CORE | {key}), [])
    validate_capabilities(sorted(CORE | with_dependencies({key})), [])


# --- deployment (platform) level ------------------------------------------------------------


def test_a_feature_whose_app_is_not_shipped_reads_off_and_cannot_be_turned_on(monkeypatch):
    ship_without(monkeypatch, "maintenance")
    assert not configuration_feature_enabled(EVERYTHING, "machines.maintenance")
    assert unavailable_features(["machines.maintenance", "machines.sessions"]) == ["machines.maintenance"]


def test_a_module_not_shipped_turns_off_every_feature_under_it(monkeypatch):
    ship_without(monkeypatch, "bookings")
    children = [key for key in LIVE if "bookings" in _closure_modules(key)]
    assert children
    for key in children:
        assert not configuration_feature_enabled(EVERYTHING, key), key
    assert set(unavailable_features(children)) == set(children)
    assert configuration_feature_enabled(EVERYTHING, "staff.invitations")


def test_retired_switches_are_never_turnable_on():
    assert unavailable_features(sorted(RETIRED_FEATURES)) == sorted(RETIRED_FEATURES)
    assert unavailable_features(LIVE) == []


# --- defaults ---------------------------------------------------------------------------------


def test_modules_are_opt_in_except_core_and_member_accounts():
    assert set(default_enabled_module_keys()) == CORE | {"member_accounts"}


NEW_0120_OFF = (
    "machines.integrations", "presence.public_display", "display.anthias_push", "events.certificate_designer",
    "cards.photo_cutout", "membership.staff_cards", "membership.units", "membership.card_numbering",
    "machines.sessions", "machines.supervised_sessions", "safety.incidents", "membership.guest_passes",
)
NEW_0120_ON = (
    "events.badge_designer", "events.badge_desk_print", "events.role_badges", "events.discovery_filters",
    "events.space_insights", "email.sender_identity", "legal.space_pages", "platform.help_centre", "loans.enabled",
)


def test_new_capabilities_ship_with_the_documented_defaults():
    adapters = [key for key in FEATURES if key.startswith("machines.integrations.")]
    assert len(adapters) >= 13
    for key in (*NEW_0120_OFF, *adapters):
        assert FEATURES[key].default_enabled is False, key
    for key in NEW_0120_ON:
        assert FEATURES[key].default_enabled is True, key
    assert not any(FEATURES[key].default_enabled for key in RETIRED_FEATURES)


def test_the_front_page_is_on_by_default():
    # Decision 300: a deployment-level switch, default on in code and in both env templates.
    source = (ROOT / "backend" / "config" / "settings_credentials.py").read_text(encoding="utf-8")
    assert 'env.bool("HUB_LANDING_ENABLED", default=True)' in source
    for template in (".env.example", ".env.production.example"):
        assert re.search(r"^HUB_LANDING_ENABLED=True$", (ROOT / template).read_text(encoding="utf-8"), re.M), template
