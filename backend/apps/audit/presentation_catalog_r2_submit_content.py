"""Audit presentation for lane r2-submit-content: submission stages, shortlist gates, extensions.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time, so
these entries name the action only.
"""

from .presentation_catalog_types import P


ENTRIES = (
    P("event.submission_stages.updated", "Submission stages changed"),
    P("event.submission_stage.shortlist_applied", "Stage shortlist chosen"),
    P("event.submission_stage.shortlist_published", "Stage shortlist published"),
    P("event.submission_stage.extension_granted", "Stage deadline extended for a team"),
)
