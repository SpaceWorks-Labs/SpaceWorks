"""Every error the audit presentation drift guard can raise, driven with synthetic catalogues.

The real catalogue is checked by the build; these tests pin the guard's own logic so it cannot quietly
stop noticing drift (an unguarded guard is the failure mode this file exists to prevent).
"""

from types import SimpleNamespace

import pytest

from apps.audit import presentation_guards as guards
from apps.tenant_migration.audit_references import AuditReferenceDisposition

REQUEST_MODEL = "hardware_requests.HardwareRequest"


def entry(paths=(), refs=(), resolver=None):
    return SimpleNamespace(permitted_meta_paths=tuple(paths), request_reference_paths=tuple(refs), link_resolver=resolver)


def discovery(actions=(), meta_paths=()):
    return SimpleNamespace(actions=set(actions), meta_paths=list(meta_paths))


def site(kind, actions=(), path="p.py"):
    return SimpleNamespace(kind=kind, actions=tuple(actions), path=path)


@pytest.fixture
def world(monkeypatch):
    """A tiny consistent world: one emitted action, one catalogue entry, nothing dynamic."""
    monkeypatch.setattr(guards, "DYNAMIC_EXACT_ACTIONS", frozenset())
    monkeypatch.setattr(guards, "NON_LITERAL_META_ACTIONS", frozenset())
    monkeypatch.setattr(guards, "WRAPPER_SITE_PREFIXES", {})
    monkeypatch.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"])})
    monkeypatch.setattr(guards, "LINK_RESOLVERS", {"known": object()})
    monkeypatch.setattr(guards, "is_denied", lambda action: False)
    monkeypatch.setattr(guards, "AUDIT_META_REFERENCES", {})
    return monkeypatch


def errors(*, found=None, sites=()):
    return guards.presentation_catalog_errors(discovery=found or discovery({"a.did"}, [("a.did", "x")]), sites=list(sites))


def test_a_consistent_world_has_no_errors(world):
    assert errors() == []


def test_dynamic_exact_actions_must_match_the_discovered_sites(world):
    assert errors(sites=[site("exact", ["b.did"])])[0].startswith("DYNAMIC_EXACT_ACTIONS drifted: ['b.did']")


def test_non_literal_meta_actions_must_match_the_discovered_sites(world):
    assert any(e == "NON_LITERAL_META_ACTIONS drifted: ['c.did']" for e in errors(sites=[site("non_literal_meta", ["c.did"])]))


def test_wrapper_prefixes_must_match_the_discovered_wrapper_sites(world):
    world.setattr(guards, "WRAPPER_SITE_PREFIXES", {"w.py": ("w.",)})
    assert any(e.startswith("WRAPPER_SITE_PREFIXES drifted: ['w.py']") for e in errors())


def test_a_literal_action_without_a_catalogue_entry_is_reported(world):
    assert "literal audit actions without a catalogue entry: ['z.new']" in errors(found=discovery({"a.did", "z.new"}, [("a.did", "x")]))


def test_a_catalogue_entry_nothing_emits_is_reported(world):
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"]), "ghost.did": entry()})
    assert "catalogue entry for an action nothing emits: ghost.did" in errors()


def test_a_catalogue_entry_inside_a_reviewed_wrapper_namespace_is_allowed(world):
    world.setattr(guards, "WRAPPER_SITE_PREFIXES", {"w.py": ("ns.",)})
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"]), "ns.thing": entry()})
    assert errors(sites=[site("wrapper", path="w.py")]) == []


def test_a_wrapper_prefix_only_counts_when_its_site_was_discovered(world):
    world.setattr(guards, "WRAPPER_SITE_PREFIXES", {"w.py": ("ns.",)})
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"]), "ns.thing": entry()})
    result = errors()
    assert "catalogue entry for an action nothing emits: ns.thing" in result


def test_a_permitted_path_no_emitter_writes_is_reported(world):
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x", "never"])})
    assert "a.did: permitted path 'never' is not a literal emitted path" in errors()


def test_a_permitted_parent_path_is_reported(world):
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"])})
    found = discovery({"a.did"}, [("a.did", "x"), ("a.did", "x.child")])
    assert "a.did: permitted path 'x' is a parent, not a leaf" in errors(found=found)


def test_a_denied_action_may_not_permit_metadata(world):
    world.setattr(guards, "is_denied", lambda action: action == "a.did")
    assert "a.did: denied by the dynamic policy but permits metadata" in errors()


def test_a_denied_action_with_no_metadata_is_fine(world):
    world.setattr(guards, "is_denied", lambda action: True)
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry()})
    assert errors() == []


def _reference(disposition, model):
    return SimpleNamespace(disposition=disposition, target_model_label=model)


@pytest.mark.parametrize(
    ("references", "ok"),
    [
        ({("a.did", "x"): _reference(AuditReferenceDisposition.REMAP, REQUEST_MODEL)}, True),
        ({}, False),
        ({("a.did", "x"): _reference(AuditReferenceDisposition.REMAP, "inventory.Product")}, False),
        ({("a.did", "x"): _reference(AuditReferenceDisposition.NULL, REQUEST_MODEL)}, False),
    ],
)
def test_a_request_reference_must_be_a_declared_remap_of_a_hardware_request(world, references, ok):
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"], refs=["x"])})
    world.setattr(guards, "AUDIT_META_REFERENCES", references)
    message = "a.did: 'x' is not a declared HardwareRequest reference"
    assert (message not in errors()) is ok


def test_a_request_reference_path_must_also_be_permitted(world):
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"], refs=["other"])})
    world.setattr(guards, "AUDIT_META_REFERENCES", {("a.did", "other"): _reference(AuditReferenceDisposition.REMAP, REQUEST_MODEL)})
    assert "a.did: 'other' is not a declared HardwareRequest reference" in errors()


def test_an_unknown_link_resolver_is_reported_and_a_known_one_is_not(world):
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"], resolver="nope")})
    assert "a.did: unknown link resolver 'nope'" in errors()
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"], resolver="known")})
    assert errors() == []


def test_dynamic_exact_actions_count_as_emitted(world):
    world.setattr(guards, "DYNAMIC_EXACT_ACTIONS", frozenset({"dyn.did"}))
    world.setattr(guards, "PRESENTATION_CATALOG", {"a.did": entry(paths=["x"]), "dyn.did": entry()})
    assert errors(sites=[site("exact", ["dyn.did"])]) == []
