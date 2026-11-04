"""What the settings-authority layer knows: modules, their keys, and the fixed exceptions.

Rows only (a hot registry, LANE-RULES §18): a lane that adds a delegable module setting
appends `(module, key)` to `EXTRA_SETTING_KEYS`; a lane that adds a role allowed to edit
some keys without a grant (the Shop Manager, L22) appends a `FixedException`. Feature
switches and the domain settings fields come from `domain_settings.DOMAINS`, so the two
can never disagree about which module owns a key.
"""

from dataclasses import dataclass

from apps.accounts.rbac_actions import Action

# Settings module -> the manager action that makes someone that module's manager. The
# Event Manager holds `manage_events`, so C-11c needs no row of its own.
MODULE_MANAGER_ACTIONS = {
    "events": Action.MANAGE_EVENTS,
    "bookings": Action.MANAGE_BOOKINGS,
    "machines": Action.MANAGE_MACHINES,
    "inventory": Action.EDIT_INVENTORY,
    # L22 (#137): the shop's own settings belong to the Shop Manager.
    "shop": Action.MANAGE_SHOP,
}

# Finance settings are the Space Manager's alone and never delegable (#101, C-15/C-16).
FINANCE_MODULES = frozenset({"payments", "charges", "billing", "finance", "tax"})
FINANCE_PREFIXES = ("payments.", "charges.", "billing.", "finance.", "tax")

# C-11d: loan length, renewals, and L15's per-space rental timing.
RENTAL_TIMING_KEYS = frozenset({
    "default_loan_days", "loan_renewal_mode", "loan_max_renewals", "loan_renewal_days",
    "loans.renewals", "rental_timing",
})
# The lending policy fields `loan_policy_settings.update_loan_policy` writes.
LOAN_POLICY_KEYS = (
    "default_loan_days", "loan_renewal_mode", "loan_max_renewals", "loan_renewal_days",
    "loan_max_active", "loan_max_items", "loan_reminder_offsets_hours", "loan_escalate_overdue_days",
)


@dataclass(frozen=True)
class FixedException:
    module: str
    keys: frozenset
    action: str
    reason: str


# L22 (#137): the shop's own switches and settings (tax classes, holds, the returns window,
# ...). `charges.shop` and `payments.shop` are finance settings and stay Space-Manager-only.
SHOP_SWITCH_KEYS = (
    "shop.online", "shop.guest_checkout", "shop.holds", "shop.member_prices", "shop.tax", "shop.returns",
    "shop.cash_up", "shop.event_pickup", "shop.order_limits", "shop.public_stock", "shop.receipts",
    "shop.reorder", "shop.bundles", "shop.consumable_link",
)
SHOP_SETTING_KEYS = (
    "shop_online_hold_minutes", "shop_desk_hold_hours", "shop_returns_window_days", "shop_first_reminder_days",
    "shop_second_reminder_days", "shop_uncollected_cancel_days", "shop_policy_text", "shop_pickup_note",
)

FIXED_EXCEPTIONS = (
    FixedException("inventory", RENTAL_TIMING_KEYS, Action.EDIT_INVENTORY,
                   "The Inventory Manager always sets rental timing (#128 C-11d)."),
    FixedException("shop", frozenset((*SHOP_SWITCH_KEYS, *SHOP_SETTING_KEYS)), Action.MANAGE_SHOP,
                   "The Shop Manager edits the shop's own settings without a grant (#137)."),
)

# (module, key) rows appended by later lanes for settings outside `domain_settings`.
EXTRA_SETTING_KEYS = (
    *(("inventory", key) for key in LOAN_POLICY_KEYS),
    ("inventory", "rental_timing"),
    # L1: DY-61 puts the two event report switches under the Event Manager's grant
    # (#101, #128 C-11c), and the event embed allow-list is an events setting.
    ("events", "reports.event_pdf"),
    ("events", "reports.event_exports"),
    ("events", "event_embed_policy"),
    # L15: each area's rate card is that module's setting (#101 names the L15 pricing
    # defaults); rental timing is registered above under the C-11d fixed exception.
    ("inventory", "pricing.loans"),
    ("machines", "pricing.machines"),
    ("bookings", "pricing.bookings"),
    ("events", "pricing.events"),
    # L12: loan pickup windows and the waitlist offer (inventory module settings).
    ("inventory", "pickup_window_hours"),
    ("inventory", "reservation_max_days_ahead"),
    ("inventory", "waitlist_offer_hours"),
    # L12: per-machine-type job settings (#140/#142); the `charges.*` ones are finance (SM only).
    ("machines", "job_requests.accepts"),
    ("machines", "job_requests.limits"),
    ("machines", "job_requests.unattended"),
    ("machines", "job_requests.file_formats"),
    ("machines", "charges.machines_quotes"),
    ("machines", "charges.machines_payment_timing"),
    ("machines", "charges.machines_failure"),
    # L3: member-card settings and the card-design approval switch at the space level
    # (#128 C-28, #136); event card approval sits under events (the Event Manager's grant).
    ("membership", "member_cards.auto_issue"),
    ("membership", "member_cards.email_on_issue"),
    ("membership", "member_cards.public_verify"),
    ("membership", "member_cards.verify_show_plan"),
    ("membership", "card_designs.approval"),
    ("events", "card_designs.approval"),
    # L22: the shop's own settings (the `shop.*` switches come from `domain_settings`).
    *(("shop", key) for key in SHOP_SETTING_KEYS),
)


def is_finance_setting(module, key):
    return module in FINANCE_MODULES or key.startswith(FINANCE_PREFIXES)


def setting_keys(module):
    """Every known setting key of one module, switches first, in a stable order."""
    from .domain_settings import DOMAINS, feature_keys

    keys = []
    if module in DOMAINS:
        keys.extend(feature_keys(module))
        keys.extend(DOMAINS[module].settings)
    keys.extend(key for owner, key in EXTRA_SETTING_KEYS if owner == module)
    return tuple(dict.fromkeys(keys))


def module_for_key(key):
    """The settings module owning a key, or None when no module manager may own it."""
    for module in MODULE_MANAGER_ACTIONS:
        if key in setting_keys(module):
            return module
    return None
