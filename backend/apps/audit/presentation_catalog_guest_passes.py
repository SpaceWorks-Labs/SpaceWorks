"""Decision 223: guest passes and day-pass products. Ids, kinds and versions only: never the waiver text,
a revocation reason, a price or a person's name."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("membership.guest_pass_issued", gettext_noop("Guest pass issued"), ("kind", "holder_id", "sponsor_id")),
    P("membership.guest_pass_revoked", gettext_noop("Guest pass revoked"), ("kind", "refund_opened")),
    P("membership.guest_pass_kept_on_cancel", gettext_noop("Event pass kept after the registration was cancelled"),
      ("registration_id",)),
    P("membership.guest_pass_expired", gettext_noop("Guest pass expired")),
    P("membership.guest_pass_converted", gettext_noop("Guest pass converted to a membership"), ("membership_id",)),
    P("membership.guest_pass_waiver_stamped", gettext_noop("Guest pass waiver accepted"),
      ("waiver_version", "at_desk")),
    P("membership.guest_pass_charge_raised", gettext_noop("Day pass charge raised"), ("payment_id", "product_id")),
    P("membership.day_pass_product_saved", gettext_noop("Day pass product saved"), ("created", "fields")),
    P("membership.day_pass_product_archived", gettext_noop("Day pass product archived")),
    P("membership.guest_pass_charge_redirected", gettext_noop("Loan charge billed to a guest's sponsor"),
      ("request_id", "payment_id", "guest_id", "sponsor_id", "subject")),
    P("member.walk_in_guest_pass_created", gettext_noop("Walk-in registered with a guest pass"),
      ("has_email", "has_phone")),
    P("makerspace.guest_pass_policy_updated", gettext_noop("Guest pass policy changed"), ("fields",)),
)
