"""Which module group a report belongs to, so the Reports hub reads like the module screens.

The grouping is DERIVED, never stored: a report's source module (or the prefix of its capability
key) names the registry group the operator already sees on the module switches, and the coverage
table (`report_coverage`) answers for the reports that read no single module. A report with no
source at all is a loan-spine report and sits under Inventory, the always-on group.
"""

from functools import lru_cache

from apps.makerspaces.module_registry import BY_KEY, GROUPS
from apps.operations.report_sources import parts

PLATFORM_GROUP = "platform"
# Coverage areas have no installable key; each reads under the group of the thing it observes.
_AREA_GROUPS = {"presence": "membership", "audit": "reports", "organizations": "reports",
                "platform": PLATFORM_GROUP, "maintenance": "machines", "procurement": "inventory"}


def _module_group(key):
    root = parts(key)[0].split(".")[0]
    definition = BY_KEY.get(root)
    return definition.group if definition else _AREA_GROUPS.get(root)


@lru_cache(maxsize=1)
def _coverage_groups():
    from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
    found = {}
    for module, coverage in REPORT_MODULE_COVERAGE.items():
        group = _module_group(module)
        for key in coverage.reports:
            found.setdefault(key, group)
    return found


def report_group(definition):
    """The group key of one report definition (a registry group key, or ``platform``)."""
    if definition.platform_only:
        return PLATFORM_GROUP
    for key in definition.required_modules:
        group = _module_group(key)
        if group:
            return group
    if definition.required_feature:
        group = _module_group(definition.required_feature)
        if group:
            return group
    return _coverage_groups().get(definition.key) or "inventory"


def report_group_info(definition):
    """``(key, label, order)`` for the catalogue; the label is translated at the presentation seam."""
    from config.locale_resolution import display
    key = report_group(definition)
    if key == PLATFORM_GROUP:
        from django.utils.translation import gettext
        return key, gettext("Platform"), len(GROUPS)
    for order, group in enumerate(GROUPS):
        if group.key == key:
            return key, display(group.label), order
    return "inventory", display(GROUPS[0].label), 0


def catalog_group_fields(definition):
    """The three catalogue fields the hub groups by (key, translated label, display order)."""
    key, label, order = report_group_info(definition)
    return {"group": key, "group_label": label, "group_order": order}
