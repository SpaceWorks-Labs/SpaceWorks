"""Member renewal and subject-access events, with no personal metadata disclosure."""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("subject_export.requested", gettext_lazy("Personal data export requested")),
    P("subject_export.started", gettext_lazy("Personal data export started")),
    P("membership.grace_promised", gettext_lazy("Membership grace boundary recorded")),
    P("membership.renewal_checkout_attempted", gettext_lazy("Membership renewal checkout attempted"), ("attempt",)),
    P("subject_export.failed", gettext_lazy("Personal data export failed"), ("failure_code",)),
    P("subject_export.download_url_issued", gettext_lazy("Personal data export download issued"),
      ("expires_in_seconds",)),
    P("membership.renewed", gettext_lazy("Membership renewed"), ("membership_id", "term_id")),
    P("membership.renewal_retry", gettext_lazy("Membership renewal retry"), ("attempt",)),
    P("account.profile_updated", gettext_lazy("Account profile updated"), ("fields",)),
    P("account.session_revoked", gettext_lazy("Account session revoked"), ("kind", "session_hash")),
    P("membership.renewal_cancelled", gettext_lazy("Membership renewal cancelled")),
    P("membership.left", gettext_lazy("Member left makerspace")),
)
