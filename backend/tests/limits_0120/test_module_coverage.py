"""Decision 328a: every module has limit keys or an explicit exemption; every key has one home module.

A new module, or a new limit key, cannot ship unlimited by accident: this guard fails first. Written, not run, by
the LIMITS lane.
"""
from pathlib import Path

import pytest

from apps.makerspaces.limit_modules import KEY_MODULE, MODULE_EXEMPT, group_of, groups_payload, keys_of_module, module_of
from apps.makerspaces.limit_registry import ENFORCEMENT
from apps.makerspaces.limits_core import EXTRA_QUOTA_LIMIT_KEYS, KNOWN_LIMIT_KEYS
from apps.makerspaces.module_registry import BY_KEY, GROUPS
from apps.managed_hosting.extra_quota_counters import COUNTERS
from apps.managed_hosting.extra_quotas import SPECS

NEW_KEYS = (
    "hardware_requests_monthly", "stock_transfers_monthly", "stocktake_sessions_monthly",
    "reimbursement_claims_monthly", "public_page_assets", "scheduled_reports", "adapter_media_bytes",
    "adapter_telemetry_points", "anthias_players", "shelf_checks_monthly",
)
APPS = Path(__file__).resolve().parents[2] / "apps"


def test_registry_has_the_thirty_six_modules():
    # 37 until decision 340b folded `printing` into machine_service.
    assert len(BY_KEY) == 36


def test_the_print_limit_keeps_its_name_and_belongs_to_machine_service():
    # Decision 340b: `print` moved with the retired `printing` module; the key name is unchanged.
    assert module_of("print") == "machine_service"
    assert "print" in keys_of_module("machine_service")
    assert keys_of_module("printing") == []
    assert group_of("print") == "machines"


@pytest.mark.parametrize("module", sorted(BY_KEY))
def test_every_module_has_limit_keys_or_a_reasoned_exemption(module):
    keys, reason = keys_of_module(module), MODULE_EXEMPT.get(module)
    assert bool(keys) != bool(reason), f"{module}: needs limit keys OR an exemption reason, not both or neither"
    if reason:
        assert len(str(reason)) > 15


def test_no_module_key_in_the_map_is_unknown():
    assert set(KEY_MODULE.values()) <= set(BY_KEY)
    assert set(MODULE_EXEMPT) <= set(BY_KEY)


def test_every_known_limit_key_has_a_home_module_and_group():
    assert set(KEY_MODULE) == set(KNOWN_LIMIT_KEYS)
    for key in KNOWN_LIMIT_KEYS:
        assert module_of(key) in BY_KEY and group_of(key), key


def test_groups_follow_the_module_switch_screen_order():
    order = [g.key for g in GROUPS]
    payload = [g["key"] for g in groups_payload()]
    assert payload == [key for key in order if key in payload]
    assert {group_of(key) for key in KNOWN_LIMIT_KEYS} == set(payload)


@pytest.mark.parametrize("key", NEW_KEYS)
def test_each_new_key_is_registered_everywhere(key):
    assert key in EXTRA_QUOTA_LIMIT_KEYS and key in SPECS and key in COUNTERS and key in ENFORCEMENT
    path, needle = ENFORCEMENT[key]
    assert needle in (APPS / path).read_text(encoding="utf8"), f"{key}: enforcement point {path} lost {needle!r}"


def test_counter_table_matches_specs():
    assert set(COUNTERS) == set(SPECS)
