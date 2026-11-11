"""Every per-space limit key: its console area and WHERE it is enforced (owner 2026-11-11).

Default for every key is NO limit (nothing stored); the superadmin sets values per space in
``resource_limit_overrides`` and a set value applies to the space whether it is own or hosted.
A limit only ever refuses the START of something new (typed 409 / the existing refusal): it never
blocks reading or exporting data, settling an existing charge, recording a debt, refunds, returns
of issued items, or member data and privacy requests.

``ENFORCEMENT`` is the coverage registry: key -> (file under ``backend/apps``, text that file must
contain). A guard test fails when a known key has no entry or its enforcement point disappears.
"""
from django.utils.translation import gettext_noop

AREA_LABELS = {
    "people": gettext_noop("People"), "inventory": gettext_noop("Inventory"), "machines": gettext_noop("Machines"),
    "events": gettext_noop("Events"), "bookings": gettext_noop("Bookings"), "shop": gettext_noop("Shop"),
    "money": gettext_noop("Money"), "messaging": gettext_noop("Messaging"),
    "integrations": gettext_noop("Integrations"), "storage": gettext_noop("Storage"),
}
AREA_ORDER = tuple(AREA_LABELS)

_CHANNEL = ("makerspaces/limits_reservations.py", "reserve_notification_quota")
ENFORCEMENT = {
    # People
    "members": ("makerspaces/membership_activation.py", '"members"'),
    "staff": ("accounts/staff_account_policy.py", '"staff"'),
    "guest_passes": ("makerspaces/guest_pass_issue.py", '"guest_passes"'),
    # Inventory
    "products": ("admin_api/serializers_inventory_products.py", '"products"'),
    "assets": ("boxes/api_views_external.py", '"assets"'),
    # Machines
    "machines": ("admin_api/views_machines.py", "'machines'"),
    "print": ("machines/job_intake.py", '"print"'),
    "machine_service_open": ("machines/service_workflow_actions.py", '"machine_service_open"'),
    "machine_service_submit": ("machines/service_workflow_actions.py", '"machine_service_submit"'),
    # Events and bookings
    "events": ("events/services_lifecycle.py", '"events"'),
    "events_monthly": ("makerspaces/limits_check.py", "check_space_quota"),
    "bookings": ("bookings/services_bookings.py", "'bookings'"),
    "bookings_monthly": ("makerspaces/limits_check.py", "check_space_quota"),
    # Money (new paid transactions only; see space_quotas.require_payment_capacity)
    "payments_monthly_count": ("payments/pricing/charging.py", "require_payment_capacity"),
    "payments_monthly_amount": ("payments/pricing/charging.py", "require_payment_capacity"),
    "platform_payments_monthly_count": ("payments/checkout_coordination.py", "rail_refusal"),
    "platform_payments_monthly_amount": ("payments/checkout_coordination.py", "rail_refusal"),
    # Messaging
    "email": ("integrations/dispatch_outbox.py", '"email"'),
    "telegram": _CHANNEL, "slack": _CHANNEL, "mattermost": _CHANNEL, "discord": _CHANNEL, "webhook": _CHANNEL,
    "native_push": _CHANNEL, "sms": _CHANNEL, "whatsapp": _CHANNEL,
    "platform_email_monthly": ("integrations/dispatch_outbox.py", "channel_refusal"),
    "platform_sms_monthly": _CHANNEL, "platform_whatsapp_monthly": _CHANNEL, "platform_push_monthly": _CHANNEL,
    "platform_wallet_monthly": ("card_designs/wallet/service.py", "platform_wallet_monthly"),
    # Integrations
    "api_clients": ("admin_api/api_client_views.py", '"api_clients"'),
    "data_exports": ("data_export/services.py", '"data_exports"'),
    "custom_domain": ("makerspaces/limits_usage.py", "custom_domain_allowed"),
    # Storage
    "storage": ("makerspaces/limits_uploads.py", '"storage"'),
    "upload_bytes": ("makerspaces/limits_uploads.py", '"upload_bytes"'),
    # Decision 284 addendum: every other countable resource. One call per key into extra_quotas.
    "event_registrations_monthly": ("events/services_registration.py", "event_registrations_monthly"),
    "shop_orders_monthly": ("shop/orders_core.py", "shop_orders_monthly"),
    "shop_products": ("shop/services_catalogue.py", "shop_products"),
    "membership_plans": ("admin_api/views_membership_plans.py", "membership_plans"),
    "donation_campaigns": ("payments/donations/views_staff.py", "donation_campaigns"),
    "bookable_spaces": ("bookings/services_spaces.py", "bookable_spaces"),
    "boxes": ("boxes/api_views_qr.py", '"boxes"'),
    "organizations_linked": ("organizations/services_owner.py", "organizations_linked"),
    "api_requests_per_minute": ("apiclients/throttling.py", "api_requests_per_minute"),
    "analytics_connections": ("analytics/services.py", "analytics_connections"),
    "report_exports_monthly": ("operations/report_download.py", "report_exports_monthly"),
    "kiosk_stations": ("makerspaces/kiosk_station_services.py", "kiosk_stations"),
    "devices": ("devices/services_identity.py", '"devices"'),
    "machine_jobs_monthly": ("machines/service_workflow_actions.py", "machine_jobs_monthly"),
    "machine_sessions_monthly": ("machines/sessions_service.py", "machine_sessions_monthly"),
    "storage_evidence_bytes": ("makerspaces/limits_uploads.py", "storage_evidence_bytes"),
    "storage_public_images_bytes": ("makerspaces/limits_uploads.py", "storage_public_images_bytes"),
    "webhook_endpoints": ("admin_api/views_notification_destinations.py", "webhook_endpoints"),
    "member_cards_issued_monthly": ("makerspaces/member_card_services.py", "member_cards_issued_monthly"),
    "wallet_passes": ("card_designs/wallet/service.py", "wallet_passes"),
    "staff_cards_issued_monthly": ("card_designs/staff_card_services.py", "staff_cards_issued_monthly"),
    "member_units": ("makerspaces/member_units.py", "member_units"),
    "series_invites": ("events/series_invites.py", "series_invites"),
    "checkin_lists": ("events/checkin_lists.py", "checkin_lists"),
    "event_badge_prints_monthly": ("events/badge_prints.py", "event_badge_prints_monthly"),
    "hackathon_stages": ("events/submissions/stage_rules.py", "check_scoped_quota"),
    "saved_views": ("operations/saved_view_events.py", "saved_views"),
    "collection_sheet_rows_monthly": ("payments/collection_sheet.py", "collection_sheet_rows_monthly"),
}

AREA_OF = {
    "members": "people", "staff": "people", "guest_passes": "people",
    "products": "inventory", "assets": "inventory",
    "machines": "machines", "print": "machines", "machine_service_open": "machines",
    "machine_service_submit": "machines",
    "events": "events", "events_monthly": "events", "bookings": "bookings", "bookings_monthly": "bookings",
    "payments_monthly_count": "money", "payments_monthly_amount": "money",
    "platform_payments_monthly_count": "money", "platform_payments_monthly_amount": "money",
    "email": "messaging", "telegram": "messaging", "slack": "messaging", "mattermost": "messaging",
    "discord": "messaging", "webhook": "messaging", "native_push": "messaging", "sms": "messaging",
    "whatsapp": "messaging", "platform_email_monthly": "messaging", "platform_sms_monthly": "messaging",
    "platform_whatsapp_monthly": "messaging", "platform_push_monthly": "messaging",
    "platform_wallet_monthly": "messaging",
    "api_clients": "integrations", "data_exports": "integrations", "custom_domain": "integrations",
    "storage": "storage", "upload_bytes": "storage",
    "event_registrations_monthly": "events", "shop_orders_monthly": "shop", "shop_products": "shop",
    "membership_plans": "people", "donation_campaigns": "money", "bookable_spaces": "bookings",
    "boxes": "inventory", "organizations_linked": "people", "api_requests_per_minute": "integrations",
    "analytics_connections": "integrations", "report_exports_monthly": "integrations",
    "kiosk_stations": "inventory", "devices": "machines", "machine_jobs_monthly": "machines",
    "machine_sessions_monthly": "machines", "storage_evidence_bytes": "storage",
    "storage_public_images_bytes": "storage", "webhook_endpoints": "integrations",
    "member_cards_issued_monthly": "people", "wallet_passes": "people", "member_units": "people",
    "staff_cards_issued_monthly": "people",
    "series_invites": "events", "checkin_lists": "events", "saved_views": "events", "hackathon_stages": "events",
    "event_badge_prints_monthly": "events",
    "collection_sheet_rows_monthly": "money",
}


def area_of(key) -> str:
    return AREA_OF.get(key, "integrations")
