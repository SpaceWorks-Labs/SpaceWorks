"""Build the /control/ sidebar from the catalogue in ``config.control_catalog``.

``config.unfold`` passes in its three item builders so the gates stay where they were:

* ``item``: every active superadmin (the U-SEC rule for the whole console);
* ``managed``: a managed deployment only (``PLATFORM_DOMAIN_SUFFIX``) -- hosting requests and
  the platform Stripe Connect account, as before;
* ``plans``: only while the managed-hosting limiter is on (``MANAGED_PLANS_ENABLED``, #187A) --
  hosting plans, space plans and hosting invoices. Per-space limits and quotas apply to every
  space (decisions 281/284), so the rest of "Limits & hosting" is never gated on plans.

A model of a separable app carries that app's label so ``item`` can drop the entry when the
app is tombstoned (a stale ``reverse_lazy`` would 500 the whole console). The payments
provider settings belong to the separable RAIL, ``payments_rail``, not to the core ledger.
"""

from apps.separability.tombstones import SEPARABLE_APPS
from config.control_catalog import SECTIONS

MANAGED_ONLY = frozenset({"hosting_requests.hostingrequest", "payments.platformstripeconnectsettings"})
PLANS_ONLY = frozenset({"managed_hosting.hostingplan", "managed_hosting.spaceplanassignment",
                        "managed_hosting.hostinginvoice"})
SEPARABLE_OWNER = {"payments": "payments_rail"}
# Ledger models of the core `payments` app: never tombstoned, whatever happens to the rail.
CORE_LEDGER = frozenset({"payments.payment", "payments.manualsettlement", "payments.refund", "payments.refundcase",
                         "payments.paymentdispute", "payments.ledgerentry", "payments.donation",
                         "payments.donationcampaign"})


def separable_app(entry):
    if not entry.is_model or entry.key in CORE_LEDGER:
        return None
    app_label = entry.key.split(".")[0]
    owner = SEPARABLE_OWNER.get(app_label, app_label)
    return owner if owner in SEPARABLE_APPS else None


def _builder(entry, item, managed, plans):
    if entry.key in MANAGED_ONLY:
        return managed
    if entry.key in PLANS_ONLY:
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
        groups.append({"title": section.title, "separator": True, "collapsible": True,
                       "section": section.key, "icon": section.icon, "items": items})
    return groups
