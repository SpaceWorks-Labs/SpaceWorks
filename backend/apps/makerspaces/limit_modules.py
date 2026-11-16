"""Which module owns each limit key, and why a module has none (decision 328a, 0.12.0).

The superadmin and Space Manager limit screens group by MODULE (the groups of ``module_groups``), not by the older
console area. ``KEY_MODULE`` gives every key in ``limits_core.KNOWN_LIMIT_KEYS`` exactly one home module;
``MODULE_EXEMPT`` names every module where no limit makes sense, with the reason. A guard test
(``tests/limits_0120/test_module_coverage.py``) fails when a registry module has neither keys nor an exemption,
or a key has no home, so a new module or key cannot ship unlimited by accident.
"""
from django.utils.translation import gettext_noop

KEY_MODULE = {
    # Inventory group
    "products": "public_inventory", "storage_public_images_bytes": "public_inventory",
    "public_page_assets": "public_inventory", "custom_domain": "public_inventory",
    "hardware_requests_monthly": "request_workflow",
    "staff": "staff_admin", "staff_cards_issued_monthly": "staff_admin",
    "guest_passes": "guest_handover", "kiosk_stations": "scanner",
    "storage": "evidence_uploads", "upload_bytes": "evidence_uploads", "storage_evidence_bytes": "evidence_uploads",
    "boxes": "qr_management", "assets": "asset_units", "stock_transfers_monthly": "stock_transfers",
    "stocktake_sessions_monthly": "stocktake", "shelf_checks_monthly": "stocktake",
    # Machines and devices
    "machines": "machines", "machine_jobs_monthly": "machines", "machine_sessions_monthly": "machines",
    # `print` keeps its name; its module is machine_service since `printing` folded in (340b).
    "print": "machine_service", "machine_service_open": "machine_service", "machine_service_submit": "machine_service",
    "devices": "devices", "adapter_bridges": "devices", "adapter_watch_streams": "devices",
    "adapter_snapshots": "devices", "adapter_artifacts": "devices", "adapter_media_bytes": "devices",
    "adapter_telemetry_points": "devices",
    # Events and bookings
    "events": "events", "events_monthly": "events", "event_registrations_monthly": "events",
    "series_invites": "events", "checkin_lists": "events", "event_badge_prints_monthly": "events",
    "hackathon_stages": "events", "saved_views": "events",
    "reimbursement_claims_monthly": "event_reimbursements",
    "bookings": "bookings", "bookings_monthly": "bookings", "bookable_spaces": "bookings",
    # Membership
    "members": "membership", "membership_plans": "membership", "organizations_linked": "membership",
    "member_cards_issued_monthly": "membership", "wallet_passes": "membership", "member_units": "membership",
    "photo_cutout_jobs_monthly": "membership", "card_templates": "membership",
    "platform_wallet_monthly": "membership", "paired_displays": "presence", "anthias_players": "presence",
    # Notifications and mobile
    "email": "email", "platform_email_monthly": "email", "telegram": "telegram", "slack": "slack",
    "mattermost": "mattermost", "discord": "discord", "webhook": "webhook", "webhook_endpoints": "webhook",
    "sms": "sms", "platform_sms_monthly": "sms", "whatsapp": "whatsapp", "platform_whatsapp_monthly": "whatsapp",
    "native_push": "mobile", "platform_push_monthly": "mobile",
    "api_clients": "notifications", "api_requests_per_minute": "notifications",
    # Reports and analytics
    "report_exports_monthly": "reports", "scheduled_reports": "reports", "data_exports": "reports",
    "analytics_connections": "analytics",
    # Payments and shop
    "payments_monthly_count": "payments", "payments_monthly_amount": "payments",
    "platform_payments_monthly_count": "payments", "platform_payments_monthly_amount": "payments",
    "donation_campaigns": "payments", "collection_sheet_rows_monthly": "payments",
    "shop_orders_monthly": "shop", "shop_products": "shop",
}

# A module with no limit of its own, and why. Shown nowhere in the UI; read by the guard test and the docs.
MODULE_EXEMPT = {
    "bulk_import": gettext_noop("Creates products and assets, which their own limits already cap."),
    "containers": gettext_noop("Containers are QR boxes and are counted by the boxes limit."),
    "qr_print_batches": gettext_noop("Label sheets are made from existing boxes and are not stored."),
    "member_accounts": gettext_noop("Sign-in accounts are counted by the members limit."),
}


def module_of(key) -> str:
    return KEY_MODULE.get(key, "")


def keys_of_module(module) -> list[str]:
    return sorted(key for key, owner in KEY_MODULE.items() if owner == module)


def group_of(key) -> str:
    """The module GROUP (`module_groups` / switch-screen heading) a key is shown under; "" when unmapped."""
    from apps.makerspaces.module_registry import BY_KEY

    definition = BY_KEY.get(module_of(key))
    return definition.group if definition else ""


def groups_payload():
    """Group key + translated label, in the order of the module switch screens (groups with no key are left out)."""
    from django.utils.translation import gettext

    from apps.makerspaces.module_registry import GROUPS

    used = {group_of(key) for key in KEY_MODULE}
    return [{"key": g.key, "label": gettext(g.label)} for g in GROUPS if g.key in used]
