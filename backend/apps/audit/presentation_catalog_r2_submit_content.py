"""Audit presentation for lane r2-submit-content: submission stages, shortlist gates, extensions.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time, so
these entries name the action only.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("event.submission_stages.updated", gettext_noop("Submission stages changed")),
    P("event.submission_stage.shortlist_applied", gettext_noop("Stage shortlist chosen")),
    P("event.submission_stage.shortlist_published", gettext_noop("Stage shortlist published")),
    P("event.submission_stage.extension_granted", gettext_noop("Stage deadline extended for a team")),
    P("event.submission_stage.shortlist_promoted", gettext_noop("Next team promoted onto a stage shortlist")),
)
