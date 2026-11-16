"""Release-2 lane L25 (#163B): the `analytics` module, an owner-approved new top-level key.

Off by default and dependency-free. It gives the space a read-only database login over
curated analytics views and embeds its Metabase dashboards in the staff console. Off means
the console tab and every analytics route answer 404 and the space's views return no rows;
the connection row and the database login are kept, so switching it back on restores both.
"""

from .module_registry_definitions import GROUP_REPORTS, GUARD, ModuleDefinition

MODULES = (ModuleDefinition(
    "analytics", "Analytics (Metabase, Grafana)",
    "A read-only database login over curated, versioned analytics views and the space's "
    "Metabase dashboards embedded in the staff console.",
    "analytics", GUARD, group=GROUP_REPORTS,
),)
