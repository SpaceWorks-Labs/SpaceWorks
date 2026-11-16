"""Frozen mapping policy: direct grants never widen outside E1/E2."""
import itertools

import pytest

from apps.makerspaces.role_migration_mapping import (
    FROZEN_BY_SLUG, LEGACY_HANDOUT_ACTIONS, classify_role, map_role,
)

SM = FROZEN_BY_SLUG["space_manager"][3]
IM = FROZEN_BY_SLUG["inventory_manager"][3]
HO = FROZEN_BY_SLUG["handover"][3]


@pytest.mark.parametrize("classification,slug,raw,expected,tags,gains", [
    ("legacy", None, (), [], [], set()),
    ("foreign", "space_manager", SM, ["member"], [], set()),
    ("catalogue_default", "space_manager", SM, ["space_manager"], [], set()),
    ("catalogue_default", "inventory_manager", IM, ["inventory_manager"], [], set()),
    ("catalogue_default", "machine_manager", {"manage_machines"}, ["machine_manager"], [], set()),
    ("catalogue_default", "member", (), ["member"], [], set()),
    ("catalogue_default", "space_manager", {"manage_makerspace"}, ["space_manager"], ["E1"], SM - {"manage_makerspace"}),
    ("obsolete", "all-sm-actions", SM, ["inventory_manager", "machine_manager", "event_manager", "booking_manager"], [], set()),
    ("obsolete", "desk", LEGACY_HANDOUT_ACTIONS, ["handover"], ["E2"], {"collect_service_request"}),
    ("obsolete", "desk-collect", HO, ["handover"], [], set()),
    ("obsolete", "inventory-events", IM | {"manage_events"}, ["inventory_manager", "event_manager"], [], set()),
    ("catalogue_default", "inventory_manager", IM | {"manage_bookings"}, ["inventory_manager", "booking_manager"], [], set()),
    # IM is a strict superset of the six old handout actions, but Handover adds
    # collect_service_request. Once collect is already stored, both remain needed.
    ("obsolete", "inventory-collect", IM | HO, ["inventory_manager", "handover"], [], set()),
    ("obsolete", "partial", {"view_inventory", "manage_qr"}, ["member"], [], set()),
])
def test_mapping_branches(classification, slug, raw, expected, tags, gains):
    result = map_role(classification=classification, slug=slug, raw_grants=raw)
    assert result["to_roles"] == expected
    assert result["primary_slug"] == (expected[0] if expected else None)
    assert result["additional_slugs"] == expected[1:]
    assert result["exception_tags"] == tags
    assert set(result["gained_actions"]) == gains
    if classification != "legacy":
        after = set().union(*(FROZEN_BY_SLUG[key][3] for key in expected))
        assert set(result["dropped_actions"]) == set(raw) - after


@pytest.mark.parametrize("raw,types,machines,all_types,outcome,to_types,roles", [
    ({"manage_machines"}, [3, 1, 3], [9], [], "copy_type_ids", [1, 3], ["machine_manager"]),
    ({"manage_machines", "manage_makerspace"}, [1], [9], [7, 2, 7], "enumerate_all_types", [2, 7], ["machine_manager"]),
    ({"manage_machines"}, [], [9], [2], "machine_manager_dropped: machine-only scope", [], ["member"]),
    ({"manage_machines"}, [], [], [2], "unchanged_empty", [], ["machine_manager"]),
])
def test_machine_scope_outcomes(raw, types, machines, all_types, outcome, to_types, roles):
    result = map_role(classification="obsolete", raw_grants=raw, type_ids=types,
                      machine_ids=machines, all_type_ids=all_types)
    assert result["to_roles"] == roles
    assert result["machine_scope_outcome"] == outcome
    assert result["machine_scope"]["to"] == {"types": to_types, "machines": []}
    assert result["machine_scope"]["dropped_machine_ids"] == machines
    assert result["machine_scope"]["exempt_enumerated"] == (outcome == "enumerate_all_types")


@pytest.mark.parametrize("role,expected", [
    (None, "legacy"),
    ({"makerspace_id": 2, "slug": "space_manager", "is_default": True}, "foreign"),
    ({"makerspace_id": 1, "slug": "inventory_manager", "is_default": True}, "catalogue_default"),
    ({"makerspace_id": 1, "slug": "inventory_manager", "is_default": False}, "obsolete"),
    ({"makerspace_id": 1, "slug": "print_manager", "is_default": True}, "obsolete"),
])
def test_original_row_classification(role, expected):
    assert classify_role(role, 1) == expected


def test_never_widen_for_all_catalogue_unions_and_partial_grants():
    grants = [entry[3] for entry in FROZEN_BY_SLUG.values()]
    samples = [set(combo) for size in (0, 1, 2) for combo in itertools.combinations(SM | HO, size)]
    samples += [set().union(*combo) for size in range(1, len(grants) + 1)
                for combo in itertools.combinations(grants, size)]
    for raw in samples:
        for classification, slug in (("obsolete", "custom"), ("catalogue_default", "inventory_manager"),
                                     ("catalogue_default", "space_manager")):
            result = map_role(classification=classification, slug=slug, raw_grants=raw)
            allowed = set()
            if "E1" in result["exception_tags"]:
                allowed |= SM - raw
            if "E2" in result["exception_tags"]:
                allowed.add("collect_service_request")
            assert set(result["gained_actions"]) <= allowed
            # The resulting set contains no role whose complete grants are
            # already supplied by another selected role.
            selected = result["to_roles"]
            for first, second in itertools.permutations(selected, 2):
                assert not FROZEN_BY_SLUG[first][3] <= FROZEN_BY_SLUG[second][3]
            if classification == "obsolete":
                assert "space_manager" not in result["to_roles"]


def test_unknown_classification_is_rejected():
    with pytest.raises(ValueError, match="Unknown original role classification"):
        map_role(classification="guess")
