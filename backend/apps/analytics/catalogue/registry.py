"""The registered analytics view domains and the catalogue version.

Each domain is ONE module exposing ``VIEWS``; a later lane adds its domain by appending one
entry to ``DOMAIN_MODULES`` and bumping ``VIEWS_VERSION``. Views of an app that is not
installed (tombstoned) are skipped, never an error.

Versioning: ``VIEWS_VERSION`` goes up whenever a view or column is added, renamed, removed
or changes meaning; ``View.since`` records the version that introduced a view. Removing or
renaming a column is a breaking change for saved Metabase questions, so prefer adding.
docs/analytics-views.md documents every view and column of the current version.
"""

from importlib import import_module

VIEWS_VERSION = 3

DOMAIN_MODULES = (
    "inventory",
    "machines",
    "bookings",
    "events",
    "tickets",
    "membership",
    "payments",
    "procurement",
    # Catalogue version 2: release 2 L18 and L22 (L21a/L21b views joined events.py).
    "donations",
    "shop",
    # Catalogue version 3: release 0.12 contextual loans, included hours, guest passes, incidents.
    "lending_contexts",
    "access_safety",
    # Release 0.12 (decision 327): machine grants, device adapters, card jobs, event certificates.
    "release_devices_cards",
)


def all_views():
    views = []
    for name in DOMAIN_MODULES:
        views.extend(import_module(f"apps.analytics.catalogue.{name}").VIEWS)
    names = [view.name for view in views]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ValueError(f"Duplicate analytics view names: {sorted(duplicates)}")
    return tuple(views)


def installed_views():
    return tuple(view for view in all_views() if view.installed())
