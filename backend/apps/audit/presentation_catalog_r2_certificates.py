"""Audit presentation for lane r2-idcards-best certificates (#199).

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time,
so these entries name the action only.
"""

from .presentation_catalog_types import P


ENTRIES = (
    P("event.certificate_signatory_saved", "Certificate signatory added or changed"),
    P("event.certificate_signatory_removed", "Certificate signatory removed"),
    P("event.certificate_signatory_approval_policy_changed", "Certificate signatory approval switched"),
    P("event.certificate_design_approved", "Certificate design approved by a signatory"),
    P("event.certificate_png_downloaded", "Event certificate image downloaded"),
    P("event.certificate_share_image_downloaded", "Event certificate share image downloaded"),
    P("event.certificate_holder_name_changed", "Certificate holder name visibility changed"),
)
