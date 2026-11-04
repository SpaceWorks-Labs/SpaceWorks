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
# Page/handle OneToOne makerspace fields are tenant ownership roots, so their
# uniqueness is tenant-scoped; ordinary FK projection already remaps those owners.
DEPLOYMENT_GLOBAL_UNIQUE_RULES = {
    ("makerspaces.MakerspacePublicPageAsset", "field:object_key"): _policy(REMAP, "Verified private-object journal allocates keys."),
    ("events.EventSession", "field:identity"): _policy(REMAP, "One working row per remapped durable session identity."),
    ("makerspaces.PublicHandle", "field:organization"): _policy(REMAP, "Global organization claims never travel."),
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
from .unique_values_events_programme import RULES as PROGRAMME_UNIQUE_RULES
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(PROGRAMME_UNIQUE_RULES)
from .unique_values_reimbursements import RULES as REIMBURSEMENT_UNIQUE_RULES
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(REIMBURSEMENT_UNIQUE_RULES)
from .catalog_p2_bookings import unique_rules as _p2_booking_unique_rules
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(_p2_booking_unique_rules(PRESERVE, REMAP, _policy))
from .unique_values_r2_l1 import RULES as R2_L1_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(R2_L1_UNIQUE_RULES)
from .unique_values_r2_l5 import RULES as R2_L5_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(R2_L5_UNIQUE_RULES)
from .unique_values_r2_l4 import RULES as R2_L4_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(R2_L4_UNIQUE_RULES)
from .unique_values_r2_l15 import RULES as R2_L15_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(R2_L15_UNIQUE_RULES)
from .unique_values_l12 import RULES as L12_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(L12_UNIQUE_RULES)
from .unique_values_l3 import RULES as L3_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(L3_UNIQUE_RULES)
from .unique_values_r2_l6 import RULES as R2_L6_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(R2_L6_UNIQUE_RULES)
from .unique_values_r2_l18 import RULES as R2_L18_UNIQUE_RULES  # noqa: E402
DEPLOYMENT_GLOBAL_UNIQUE_RULES.update(R2_L18_UNIQUE_RULES)


def collision_policy(model_label, field_name):
    policy = DEPLOYMENT_GLOBAL_UNIQUE_RULES.get((model_label, f"field:{field_name}"))
    if policy and policy.disposition is PRESERVE:
        return policy
    return None


# User identity is resolved by kind, outside EXPORTED_MODELS' tenant-row risk guard.
# P4's materializer must preserve these boundaries rather than adopt staff by email.
USER_IDENTITY_UNIQUE_RULES = {
    "username": "Globally allocated; target resolves username collisions.",
    "uniq_person_email": "One address per person; resolve only an existing person, never by email alone (#65).",
    "uniq_member_phone_e164": "Member-only identity; source proofs never travel.",
    "uniq_member_telegram_id": "Member-only identity; source proofs never travel.",
    "uniq_platform_email": "Platform principals remain inert provenance, never tenant authority.",
}
