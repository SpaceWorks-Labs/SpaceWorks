"""Audit metadata IDs written by release-2 lane r2-submit-content (stages, shortlists, extensions)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_SHORTLIST = ("event.submission_stage.shortlist_applied", "event.submission_stage.shortlist_published")
_STAGE = (*_SHORTLIST, "event.submission_stage.extension_granted", "event.submission_triaged")

EDGES = {
    **_remap("events.Event", *((action, "event_id") for action in (
        *_SHORTLIST, "event.submission_stage.extension_granted", "event.submission_stages.updated"))),
    **_remap("events.SubmissionStage", *((action, "stage_id") for action in _STAGE)),
    **_remap("events.StageShortlist", ("event.submission_stage.shortlist_published", "shortlist_id")),
    **_remap("events.HackathonTeam", ("event.submission_stage.extension_granted", "team_id")),
}
