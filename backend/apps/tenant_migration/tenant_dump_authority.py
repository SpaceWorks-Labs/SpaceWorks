"""Deny-by-default authority/disclosure overrides for the Lane D catalog."""

from .tenant_dump_types import AuthorityDisposition as D
from .tenant_dump_types import authority
from .tenant_dump_authority_entries import AUTHORITY_ENTRIES
from .tenant_dump_modules import MODULE_AUTHORITY_ENTRIES
from .target_projection_w7_events import EVENT_AUTHORITY_ENTRIES
from .catalog_wp3 import wp3_authority
from .authority_wp4 import AUTHORITY_ENTRIES as WP4_AUTHORITY_ENTRIES
from .catalog_broadcasts import authority_entries as broadcast_authority
from .catalog_messaging import authority_entries as messaging_authority

from .catalog_profiles import authority_entries as profile_authority
from .catalog_public_pages import authority_entries as page_authority
from .catalog_account_context import AUTHORITY_ENTRIES as ACCOUNT_CONTEXT_AUTHORITY
from .target_projection_events_programme import TARGET_FIELDS as PROGRAMME_TARGET_FIELDS
from .target_projection_reimbursements import TARGET_FIELDS as REIMBURSEMENT_TARGET_FIELDS

def _build(entries):
    result = {}
    for edge, rule in entries:
        if edge in result:
            raise RuntimeError(f"duplicate Lane D authority rule: {edge}")
        result[edge] = rule
    return result


AUTHORITY_FIELD_OVERRIDES = _build((
    *((edge, authority(D.RESET, policy.reason)) for edge, policy in PROGRAMME_TARGET_FIELDS.items()),
    *((edge, authority(D.RESET, policy.reason)) for edge, policy in REIMBURSEMENT_TARGET_FIELDS.items()),
    *AUTHORITY_ENTRIES,
    *ACCOUNT_CONTEXT_AUTHORITY,
    *profile_authority(authority, D),
    *page_authority(authority, D),
    (("events.EventPage", "draft_revision"), authority(D.PRESERVE, "Remapped current draft restored by allowlisted pointer fixup.")),
    (("events.EventPage", "published_revision"), authority(D.RESET, "Target publication requires fresh release.")),
    (("events.EventPage", "editorial_document"), authority(D.PRESERVE, "Authored presentation with explicit disclosure resets.")),
    (("events.EventSession", "identity"), authority(D.PRESERVE, "Remapped page-owned durable session identity.")),
    (("bookings.BookingResourcePage", "released"), authority(D.RESET, "Target staff explicitly release imported resource content.")),
    (("bookings.BookingResourcePageSection", "visibility"), authority(D.PRESERVE, "Editorial intent travels behind reset release.")),
    *((("bookings.Booking", field), authority(D.PRESERVE,
        "Historical cancellation provenance; undo still requires live target authority, clock and exact ordinary admission."))
      for field in ("cancelled_at", "status_before_cancel")),
    (("events.EventPage", "released"), authority(D.RESET, "Target staff authorize website release.")),
    (("events.EventPage", "section_enabled"), authority(D.PRESERVE, "Curated presentation travels behind reset page release.")),
    (("makerspaces.Makerspace", "website_embed_origins"), authority(D.RESET, "Target staff establish framing trust.")),
    (("events.EventPageSection", "visibility"), authority(D.PRESERVE, "Curated section intent travels behind the reset page release.")),
    (("events.EventSession", "visibility"), authority(D.PRESERVE, "Curated schedule intent travels behind the reset page release.")),
    *EVENT_AUTHORITY_ENTRIES,
    *MODULE_AUTHORITY_ENTRIES,
    *wp3_authority(authority, D).items(),
    *WP4_AUTHORITY_ENTRIES,
    *broadcast_authority(authority, D),
    *messaging_authority(authority, D),
))
NON_MODEL_AUTHORITY_INPUTS = {
    "target_native_app_registrations": authority(D.RESET, "Use exact target configuration."),
    "target_api_client_approvals": authority(D.RESET, "Fresh artifact-bound host approval only."),
    "target_module_registry": authority(D.RESET, "Target code capability is authoritative."),
    "target_domain_and_origin_configuration": authority(D.RESET, "Target routing is authoritative."),
}
