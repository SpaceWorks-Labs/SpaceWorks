"""Build the /control/ sidebar (#188) from the catalogue in ``config.control_catalog``.

``config.unfold`` passes in its three item builders so the gates stay where they were:

* ``item``: every active superadmin (the U-SEC rule for the whole console);
* ``managed``: a managed deployment only (``PLATFORM_DOMAIN_SUFFIX``) -- hosting requests and
  the platform Stripe Connect account, as before;
* ``plans``: only while the managed-hosting limiter is on (``MANAGED_PLANS_ENABLED``, #187A).

A model of a separable app carries that app's label so ``item`` can drop the entry when the
app is tombstoned (a stale ``reverse_lazy`` would 500 the whole console). The payments
provider settings belong to the separable RAIL, ``payments_rail``, not to the core ledger.
"""

from django.utils.translation import gettext_lazy as _

from apps.separability.tombstones import SEPARABLE_APPS
from config.control_catalog import SECTIONS

MANAGED_ONLY = frozenset({"hosting_requests.hostingrequest", "payments.platformstripeconnectsettings"})
PLANS_ONLY_APPS = frozenset({"managed_hosting"})
SEPARABLE_OWNER = {"payments": "payments_rail"}


def separable_app(entry):
    if not entry.is_model:
        return None
    app_label = entry.key.split(".")[0]
    owner = SEPARABLE_OWNER.get(app_label, app_label)
    return owner if owner in SEPARABLE_APPS else None


def _builder(entry, item, managed, plans):
    if entry.key in MANAGED_ONLY:
        return managed
    if entry.is_model and entry.key.split(".")[0] in PLANS_ONLY_APPS:
        return plans
    return item


def build_navigation(item, managed, plans):
    groups = []
    for section in SECTIONS:
        items = []
        for entry in section.entries:
            built = _builder(entry, item, managed, plans)(
                entry.title, entry.icon, entry.route, app_label=separable_app(entry))
            if built is not None:
                built["catalog_key"] = entry.key
            items.append(built)
        groups.append({"title": _(section.title), "separator": True, "collapsible": True,
                       "section": section.key, "items": items})
    return groups
