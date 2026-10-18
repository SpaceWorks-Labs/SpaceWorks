"""Declared handling for deployment-global uniqueness during materialization."""
from .unique_values_7c import LABEL_UNIQUE_RULES
from .unique_values_7b import PRINTER_UNIQUE_RULES
from .unique_values_core import CORE_UNIQUE_RULES
from .unique_values_billing import BILLING_UNIQUE_RULES
from .unique_values_devices import DEVICE_UNIQUE_RULES
from .unique_values_events import EVENT_UNIQUE_RULES
from .unique_values_bookings import BOOKING_UNIQUE_RULES
from .unique_values_website import WEBSITE_UNIQUE_RULES
from .unique_values_policy import (  # noqa: F401 -- re-exported
    FRESH,
    NULL,
    PRESERVE,
    REMAP,
    UniqueValueDisposition,
    UniqueValuePolicy,
    ValueGenerator,
    _policy,
)

# One mapping over every rule set; a per-app extension module adds its own dict here.
DEPLOYMENT_GLOBAL_UNIQUE_RULES = {
    **CORE_UNIQUE_RULES,
    ("integrations.WhatsAppTemplateBinding", "messaging_platform_template"): _policy(
        UniqueValueDisposition.DROP_ROW,
        "Global legacy provider bindings never travel or authorize target sending.",
    ),
    ("presence.PresenceSession", "field:event_registration"): _policy(
        UniqueValueDisposition.DROP_ROW,
        "Live presence is source-local; its unique event attendance binding is dropped on import.",
    ),
    ("makerspaces.PublicHandle", "field:user"): _policy(REMAP,
        "Keep only if the remapped account has no target claim; importer drops conflicts."),
    ("makerspaces.PublicHandle", "public_handle_ci_unique"): _policy(REMAP,
        "Shared namespace lock preserves a free handle; importer drops collisions."),
    **DEVICE_UNIQUE_RULES,
    **PRINTER_UNIQUE_RULES,
    **LABEL_UNIQUE_RULES,
    **BILLING_UNIQUE_RULES,
    **EVENT_UNIQUE_RULES,
    **BOOKING_UNIQUE_RULES,
    **WEBSITE_UNIQUE_RULES,
}
from .catalog_p2_bookings import unique_rules as _p2_booking_unique_rules
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(_p2_booking_unique_rules(PRESERVE, REMAP, _policy))


def collision_policy(model_label, field_name):
    policy = DEPLOYMENT_GLOBAL_UNIQUE_RULES.get((model_label, f"field:{field_name}"))
    if policy and policy.disposition is PRESERVE:
        return policy
    return None


# User identity is resolved by kind, outside EXPORTED_MODELS' tenant-row risk guard.
# P4's materializer must preserve these boundaries rather than adopt staff by email.
USER_IDENTITY_UNIQUE_RULES = {
    "username": "Globally allocated; target resolves username collisions.",
    "uniq_member_email": "Resolve only an existing member, never a staff/platform account.",
    "uniq_member_phone_e164": "Member-only identity; source proofs never travel.",
    "uniq_member_telegram_id": "Member-only identity; source proofs never travel.",
    "uniq_member_checkin_id": "Retired member identity; never target authority.",
    "uniq_staff_space_email": "Fresh staff identity in the remapped tenant, never email adoption.",
    "uniq_platform_email": "Platform principals remain inert provenance, never tenant authority.",
}
