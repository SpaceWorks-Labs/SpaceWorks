"""Audit presentation for lane r2-submit-content: submission stages, shortlist gates, extensions.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time, so
these entries name the action only.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P


ENTRIES = (
    P("event.submission_stages.updated", gettext_lazy("Submission stages changed")),
    P("event.submission_stage.shortlist_applied", gettext_lazy("Stage shortlist chosen")),
    P("event.submission_stage.shortlist_published", gettext_lazy("Stage shortlist published")),
    P("event.submission_stage.extension_granted", gettext_lazy("Stage deadline extended for a team")),
    P("event.submission_stage.shortlist_promoted", gettext_lazy("Next team promoted onto a stage shortlist")),
)
