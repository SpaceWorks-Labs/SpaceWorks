"""Install profiles x the registry: the numbers MODULES.md and INVARIANTS.md publish (matrix P1-P4).

Both documents quoted counts that had drifted silently (32 modules, 8 or 10 default
modules, events/bookings profiles of 12). These pins give the published numbers a test to
drift against: change a profile or a default and this fails until the docs are updated too.
"""

import pytest

from apps.makerspaces.module_profiles import PROFILES, profile_modules
from apps.makerspaces.module_registry import (
    MODULE_KEYS,
    core_module_keys,
    default_enabled_module_keys,
    module_dependencies,
)

PUBLISHED_PROFILE_SIZES = {
    "minimal": 6, "workshop": 12, "lending": 16, "recommended": 19, "cloud": 23,
    "everything": 37, "full": 37, "events": 12, "bookings": 12,
}


def test_the_published_module_and_default_counts():
    # L17 (#97, C-9) retired the maintenance and procurement module keys: 38 -> 36.
    assert len(MODULE_KEYS) == 37  # - maintenance, procurement (L17), - backup (B1), + shop (L22), + analytics (L25)
    assert "presence" in MODULE_KEYS
    assert len(core_module_keys()) == 6
    assert set(default_enabled_module_keys()) == core_module_keys() | {"member_accounts"}


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_each_profile_has_its_published_size_and_is_dependency_closed(profile):
    modules = set(profile_modules(profile))

    assert len(modules) == PUBLISHED_PROFILE_SIZES[profile]
    assert core_module_keys() <= modules
    for key, required in module_dependencies().items():
        if key in modules:
            assert set(required) <= modules, (profile, key, required)


def test_the_published_module_dependencies():
    assert module_dependencies() == {
        "printing": ("machine_service",),
        "event_reimbursements": ("events",),
        "mobile": ("member_accounts",),
        "membership": ("member_accounts",),
    }
