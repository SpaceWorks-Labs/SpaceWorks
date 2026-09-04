"""Canonical registry of makerspace modules.

Single source of truth for module keys, their defaults, frontend exposure and
inter-module dependencies. The parallel hand-kept lists that used to drift apart
-- ``models.DEFAULT_ENABLED_MODULES``, ``platform.MODULE_WORKFLOWS``,
``capabilities.FEATURE_MODULES`` and the hardcoded ``printing -> machine_service``
rule -- all derive from here now.

This module must NOT import ``apps.makerspaces.models``. ``models`` imports the
derived helpers from here, so the reverse edge would be a circular import.
"""

from apps.makerspaces.module_registry_definitions import (
    FEATURE_PARENT,
    GROUP_BOOKINGS,
    GROUP_EVENTS,
    GROUP_INVENTORY,
    GROUP_KEYS,
    GROUP_MACHINES,
    GROUP_MEMBERSHIP,
    GROUP_MOBILE,
    GROUP_NOTIFICATIONS,
    GROUP_PAYMENTS,
    GROUP_REPORTS,
    GROUP_STOCKTAKE,
    GROUP_UPDATES,
    GROUPS,
    GROUPS_BY_KEY,
    GUARD,
    NONE,
    GroupDefinition,
    ModuleDefinition,
)


from apps.makerspaces.module_registry_catalog import MODULES

BY_KEY = {definition.key: definition for definition in MODULES}
MODULE_KEYS = frozenset(BY_KEY)


from apps.makerspaces import module_registry_helpers as _registry_helpers  # noqa: E402

_registry_helpers.BY_KEY = BY_KEY
_registry_helpers.GROUPS = GROUPS
_registry_helpers.GROUPS_BY_KEY = GROUPS_BY_KEY
_registry_helpers.MODULES = MODULES

from apps.makerspaces.module_registry_helpers import (  # noqa: E402
    core_module_keys,
    default_enabled_module_keys,
    dependents_of,
    group_for,
    group_is_always_on,
    group_module_keys,
    is_frontend_exposed,
    module_available,
    module_dependencies,
    module_workflows,
    modules_by_group,
    with_dependencies,
)


class ImproperlyConfiguredRegistry(Exception):
    """Raised at import time when the registry itself is inconsistent."""


def _validate_registry():
    if len(BY_KEY) != len(MODULES):
        seen, duplicates = set(), set()
        for definition in MODULES:
            (duplicates if definition.key in seen else seen).add(definition.key)
        raise ImproperlyConfiguredRegistry(f"Duplicate module keys: {sorted(duplicates)}.")
    for definition in MODULES:
        unknown = [key for key in definition.requires_modules if key not in BY_KEY]
        if unknown:
            raise ImproperlyConfiguredRegistry(
                f"{definition.key} requires unknown module(s): {', '.join(unknown)}."
            )
        if definition.is_core and definition.default_enabled:
            raise ImproperlyConfiguredRegistry(
                f"{definition.key} is core, which already implies default_enabled."
            )
        # A core module is present in EVERY makerspace and cannot be switched off. If it
        # declared a dependency on an optional key, either that key is really core (and
        # is mislabelled), or the core module stops working the moment an operator
        # uninstalls something they were told was optional. `9e496997` was that bug
        # without the declaration: core `request_workflow` hard-required a
        # MakerspaceMembership row, and the default `recommended` profile ships no
        # `membership` module -- so a fresh self-host install could not accept a public
        # borrow request at all. This catches the declared form of it at import time;
        # `tests/makerspaces/test_core_module_independence.py` covers the undeclared form.
        if definition.is_core:
            optional_requirements = [
                key
                for key in definition.requires_modules
                if key in BY_KEY and not BY_KEY[key].is_core
            ]
            if optional_requirements:
                raise ImproperlyConfiguredRegistry(
                    f"{definition.key} is core but requires optional module(s): "
                    f"{', '.join(sorted(optional_requirements))}. A core module must "
                    "work with every optional module uninstalled."
                )
        if definition.enforcement not in {GUARD, FEATURE_PARENT, NONE}:
            raise ImproperlyConfiguredRegistry(
                f"{definition.key} has unknown enforcement {definition.enforcement!r}."
            )
        if definition.group not in GROUP_KEYS:
            raise ImproperlyConfiguredRegistry(
                f"{definition.key} declares unknown group {definition.group!r}. "
                f"Known groups: {', '.join(sorted(GROUP_KEYS))}."
            )
    if len(GROUPS_BY_KEY) != len(GROUPS):
        raise ImproperlyConfiguredRegistry("Duplicate group keys.")
    for group in GROUPS:
        if not group.label or not group.description:
            raise ImproperlyConfiguredRegistry(f"Group {group.key} needs a label and description.")
        # An empty group renders as a heading an operator can click with nothing behind
        # it, which reads as a broken install rather than an unused one.
        if not group_module_keys(group.key):
            raise ImproperlyConfiguredRegistry(f"Group {group.key} contains no modules.")
    # A group declared always-on must actually be un-switchable, or the console would
    # offer a master toggle whose "off" position `_canonical_modules` immediately undoes.
    for group in GROUPS:
        if group.always_on and not any(BY_KEY[key].is_core for key in group_module_keys(group.key)):
            raise ImproperlyConfiguredRegistry(
                f"Group {group.key} claims always_on but holds no core module."
            )


_validate_registry()
