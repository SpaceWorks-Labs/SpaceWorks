"""Canonical built-in roles, in primary-assignment order."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleDefinition:
    slug: str
    name: str
    legacy_role: str | None
    granted_actions: frozenset[str]
    combinable: bool = False


ROLE_CATALOG = (
    RoleDefinition("space_manager", "Space Manager", "space_manager", frozenset({
        "accept_request", "assign_box", "edit_inventory", "issue_direct_loan",
        "issue_request", "manage_bookings", "manage_events", "manage_devices",
        "manage_machines", "manage_makerspace", "manage_members", "manage_member_cards",
        "manage_printing", "manage_qr", "record_payment", "record_reimbursement_payout", "reject_request",
        "return_request", "upload_evidence", "view_audit", "view_finance", "view_inventory",
    })),
    RoleDefinition("inventory_manager", "Inventory Manager", "inventory_manager", frozenset({
        "accept_request", "assign_box", "edit_inventory", "issue_direct_loan",
        "issue_request", "manage_qr", "reject_request", "return_request",
        "upload_evidence", "view_audit", "view_inventory",
    }), True),
    RoleDefinition("machine_manager", "Machine Manager", "machine_manager",
                   frozenset({"manage_machines"}), True),
    RoleDefinition("event_manager", "Event Manager", "event_manager",
                   frozenset({"manage_events"}), True),
    RoleDefinition("booking_manager", "Booking Manager", "booking_manager",
                   frozenset({"manage_bookings"}), True),
    RoleDefinition("handover", "Handover", "handover", frozenset({
        "view_inventory", "assign_box", "issue_request", "issue_direct_loan",
        "return_request", "upload_evidence", "collect_service_request",
    }), True),
    # Release 2 L16 (#128 C-3): works assigned repair jobs, runs scheduled maintenance and
    # sets service state within the person's coverage. No inventory, money or settings.
    RoleDefinition("technician", "Technician", "technician", frozenset({
        "work_repairs", "run_maintenance", "set_service_state",
    }), True),
    # Release 2 L22 (#137): products, stock, prices, orders, the front desk, cash-ups,
    # returns, shop reports and the shop's own settings. No other inventory, no money
    # outside the shop and no other settings.
    RoleDefinition("shop_manager", "Shop Manager", "shop_manager", frozenset({
        "manage_shop", "sell_shop", "view_shop",
    }), True),
    # Decision 242(m): the Space Manager's delegate for donations -- campaigns, gifts, pledges,
    # sponsors, donor list and receipts. No other money, no settings (the non-profit profile
    # stays the Space Manager's), and never an area manager's Finance view.
    RoleDefinition("fundraising", "Fundraising", "fundraising", frozenset({"manage_donations"}), True),
    RoleDefinition("member", "Member", None, frozenset()),
)
ROLE_BY_SLUG = {role.slug: role for role in ROLE_CATALOG}
BUILTIN_ROLE_SLUGS = tuple(ROLE_BY_SLUG)
COMBINABLE_ROLE_SLUGS = frozenset(role.slug for role in ROLE_CATALOG if role.combinable)
