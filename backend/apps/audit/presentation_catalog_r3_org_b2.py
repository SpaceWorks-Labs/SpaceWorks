"""Parity O-B2: asking an applicant for changes, and bulk actions on the member register. States, round numbers and
counts only: never the staff note to the applicant, an answer, a phone number, a state or a photo key."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("membership.changes_requested", gettext_noop("Applicant asked for changes"), ("from_state", "to_state", "round")),
    P("membership.request_resubmitted", gettext_noop("Applicant resubmitted their request"),
      ("from_state", "to_state", "round")),
    P("membership.register_bulk_applied", gettext_noop("Bulk action applied from the member register"),
      ("bulk_action", "rows", "applied", "refused")),
    P("membership.join_fields_applied", gettext_noop("Join form details applied to the member"), ("fields",)),
)
