"""Audit presentation for lane r2-idcards-best certificates (#199).

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time,
so these entries name the action only.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("event.certificate_signatory_saved", gettext_noop("Certificate signatory added or changed")),
    P("event.certificate_signatory_removed", gettext_noop("Certificate signatory removed")),
    P("event.certificate_signatory_approval_policy_changed", gettext_noop("Certificate signatory approval switched")),
    P("event.certificate_design_approved", gettext_noop("Certificate design approved by a signatory")),
    P("event.certificate_png_downloaded", gettext_noop("Event certificate image downloaded")),
    P("event.certificate_share_image_downloaded", gettext_noop("Event certificate share image downloaded")),
    P("event.certificate_holder_name_changed", gettext_noop("Certificate holder name visibility changed")),
)
