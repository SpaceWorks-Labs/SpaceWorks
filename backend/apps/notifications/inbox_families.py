"""Decision 248 / NT1: the inbox's display families, matched to the areas people work in.

The stored `feature` (the preference and routing family) is unchanged, so no preference row, template or channel
default moves. Two areas that had no inbox filter of their own are carved out of their storage family at READ time:

* `shop`   -- the shop's order and stock notices, stored as `payments` events starting `shop_`;
* `safety` -- the incident register's notices, stored as `maintenance` event `incident_reported`.

`payments` and `maintenance` then exclude those rows, so every notice sits in exactly one filter.
"""

from django.db.models import Q

SHOP, SAFETY = "shop", "safety"
VIRTUAL = (SHOP, SAFETY)
_SHOP_Q = Q(feature="payments", event__startswith="shop_")
_SAFETY_Q = Q(feature="maintenance", event="incident_reported")


def display_family(feature, event):
    if feature == "payments" and str(event).startswith("shop_"):
        return SHOP
    if feature == "maintenance" and event == "incident_reported":
        return SAFETY
    return feature


def filter_family(rows, family):
    if family == SHOP:
        return rows.filter(_SHOP_Q)
    if family == SAFETY:
        return rows.filter(_SAFETY_Q)
    if family == "payments":
        return rows.filter(feature="payments").exclude(_SHOP_Q)
    if family == "maintenance":
        return rows.filter(feature="maintenance").exclude(_SAFETY_Q)
    return rows.filter(feature=family)


def families_present(rows):
    """The families this person actually receives, in first-seen order -- the filter list shows only these."""
    seen = []
    for feature, event in rows.values_list("feature", "event").distinct():
        family = display_family(feature, event)
        if family not in seen:
            seen.append(family)
    return sorted(seen)
