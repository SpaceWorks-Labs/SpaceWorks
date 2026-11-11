"""Hack-money: what must hold before a payout is recorded (decision 301 review).

- A winner's payee details are VERIFIED first (when the space runs the claim flow, `events.prize_claims`).
- Maker-checker: the person who records a payout is not the person who verified the details, unless the
  space has a single finance person (RECORD_PAYMENT or the Event Manager's MANAGE_EVENTS), who cannot be
  asked to find a second one. Authority is unchanged (C-38): this only separates the two acts.
"""

from apps.accounts import rbac
from .errors import ProgrammeError
from .models_prize_money import HackathonPrizeClaim


def claims_flow(event):
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(event.makerspace, "events.prize_claims")


def finance_ids(makerspace_id):
    from apps.makerspaces.models import MakerspaceMembership
    ids = set()
    for row in MakerspaceMembership.staff_tracks.filter(makerspace_id=makerspace_id, status="active").select_related("user"):
        if (rbac.can(row.user, rbac.Action.RECORD_PAYMENT, makerspace_id)
                or rbac.can(row.user, rbac.Action.MANAGE_EVENTS, makerspace_id)):
            ids.add(row.user_id)
    return ids


def sole_finance_person(event, actor):
    return len(finance_ids(event.makerspace_id) | {actor.pk}) <= 1


def require_verified_claim(event, award, recipient, actor):
    """Raise unless the recipient's share has verified, uncleared payee details checked by someone else."""
    if not claims_flow(event):
        return
    from .payout_split import lineage_shares
    claim = HackathonPrizeClaim.objects.select_related("share").filter(
        share__in=lineage_shares(award).filter(member_id=recipient)).order_by("-pk").first()
    if claim is None or not claim.submitted_at or claim.cleared_at or not claim.verified_at:
        raise ProgrammeError("claim_not_verified", "Verify the winner's payee details before recording the payout.")
    if claim.verified_by_id == actor.pk and not sole_finance_person(event, actor):
        raise ProgrammeError("same_person_verified", "A second finance person must record a payout you verified.")
