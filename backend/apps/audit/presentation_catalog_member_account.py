"""Member renewal and subject-access events, with no personal metadata disclosure."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("subject_export.requested", gettext_noop("Personal data export requested")),
    P("subject_export.started", gettext_noop("Personal data export started")),
    P("membership.grace_promised", gettext_noop("Membership grace boundary recorded")),
    P("membership.renewal_checkout_attempted", gettext_noop("Membership renewal checkout attempted"), ("attempt",)),
    P("subject_export.failed", gettext_noop("Personal data export failed"), ("failure_code",)),
    P("subject_export.download_url_issued", gettext_noop("Personal data export download issued"),
      ("expires_in_seconds",)),
    P("membership.renewed", gettext_noop("Membership renewed"), ("membership_id", "term_id")),
    P("membership.renewal_retry", gettext_noop("Membership renewal retry"), ("attempt",)),
    P("account.profile_updated", gettext_noop("Account profile updated"), ("fields",)),
    P("account.session_revoked", gettext_noop("Account session revoked"), ("kind", "session_hash")),
    P("membership.renewal_cancelled", gettext_noop("Membership renewal cancelled")),
    P("membership.left", gettext_noop("Member left makerspace")),
)
