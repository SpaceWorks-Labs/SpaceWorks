"""Audit metadata IDs written by release-2 lane r2-peoples-choice (#181 S3)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_ACTIONS = ("event.peoples_choice.updated", "event.peoples_choice.ballot_cast", "event.peoples_choice.vote_voided",
            "event.peoples_choice.published")

EDGES = {
    **_remap("events.Event", *((action, "event_id") for action in _ACTIONS)),
    **_remap("events.PeoplesChoiceVote", ("event.peoples_choice.vote_voided", "vote_id")),
    **_remap("events.HackathonPrize", ("event.peoples_choice.published", "prize_id")),
    # A People's choice payout names its winning standing instead of a judged award.
    **_remap("events.PeoplesChoiceStanding", ("event.prize.payout_recorded", "peoples_choice_standing_id")),
}
