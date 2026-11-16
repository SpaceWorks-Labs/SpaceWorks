"""Loan contexts, equipment kits/plans, browser Firebase wake-ups and web telemetry."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("loan.event_context_changed", gettext_noop("Loan event context changed"), ("operation", "domain")),
    P("loan.booking_context_changed", gettext_noop("Loan booking context changed"), ("operation", "domain")),
    P("equipment.context_linked", gettext_noop("Equipment linked to an event or booking"), ("domain", "kind")),
    P("inventory.equipment_kit_created", gettext_noop("Equipment kit created"), ("version",)),
    P("inventory.equipment_kit_version_created", gettext_noop("Equipment kit version created"), ("version",)),
    P("inventory.equipment_kit_changed", gettext_noop("Equipment kit setting changed"), ("field", "value")),
    P("inventory.equipment_consumable_plan_created", gettext_noop("Consumable plan created")),
    P("notification.browser_firebase_challenge_started", gettext_noop("Browser notification sign-up started")),
    P("notification.browser_firebase_subscribed", gettext_noop("Browser notifications turned on")),
    P("notification.browser_firebase_unsubscribed", gettext_noop("Browser notifications turned off")),
    P("platform.firebase_web_settings_updated", gettext_noop("Platform Firebase web settings changed"),
      ("fields", "configured")),
    P("analytics.telemetry_updated", gettext_noop("Web telemetry settings changed"), (
        "scope", "fields", "pageview_enabled", "replay_enabled", "sentry_enabled",
        "firebase_performance_enabled",
    )),
)
