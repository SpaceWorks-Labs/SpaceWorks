"""Decision 223 (k), lane L3b: minors, guardian consent, volunteer hours and credit, organization bookings.

Ids, versions, counts, amounts and field names only: never a birth date, a guardian contact detail, a typed
signature, the consent text, a volunteer description or a staff-written note.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("makerspace.community_policy_updated", gettext_noop("Community policy changed"), ("fields",)),
    P("membership.minor_recorded", gettext_noop("Minor recorded"), ("created", "has_guardian_account")),
    P("membership.minor_cleared", gettext_noop("Minor record cleared")),
    P("membership.guardian_terms_published", gettext_noop("Guardian consent text published"), ("version",)),
    P("membership.guardian_consent_signed", gettext_noop("Guardian consent signed"), ("terms_version", "method")),
    P("membership.guardian_consent_revoked", gettext_noop("Guardian consent revoked")),
    P("membership.volunteer_hours_logged", gettext_noop("Volunteer hours logged"), ("minutes", "by_staff")),
    P("membership.volunteer_hours_decided", gettext_noop("Volunteer hours decided"), ("approved", "minutes")),
    P("membership.volunteer_hours_imported", gettext_noop("Event shift hours imported"), ("count",)),
    P("membership.volunteer_credit_created", gettext_noop("Volunteer credit earned"), ("minutes", "kind")),
    P("membership.volunteer_credit_applied", gettext_noop("Volunteer credit applied to a charge"),
      ("payment_id", "applied_amount")),
    P("membership.volunteer_credit_voided", gettext_noop("Volunteer credit voided")),
    P("booking.organization_linked", gettext_noop("Booking made for an organization")),
)
