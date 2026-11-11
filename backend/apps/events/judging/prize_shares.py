"""Hack-money G3: per-member prize splits (`events.prize_claims`).

A team decides how to share a cash prize. The LEADER proposes a split over the sealed members of
the winning snapshot; each member confirms (or declines) in the app. Staff may instead record a
split already confirmed (they heard it in the room). The leader's own share is confirmed when
proposed. Shares never exceed the prize amount, and a split is fixed once any payout stands.

With no shares the L21b default is unchanged: one payout, to the leader. Nothing here moves money:
each confirmed share is later paid by its own hand-recorded payout row.
"""

from django.utils.translation import gettext
from decimal import Decimal

from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from .boundary import command, mutation
from .errors import ProgrammeError
from .models_prize_money import HackathonPrizeShare
from .ports import runtime
from .serializers import validated
from .serializers_prize import ShareRespondInput, SplitInput


def require_claims(event):
    from .feature import require_capability
    require_capability(event, "events.prize_payouts")
    require_capability(event, "events.prize_claims")


def award_total(award):
    if award.prize.kind != "cash" or award.prize.funding != "space":
        raise ProgrammeError("prize_not_split", gettext("Only a cash prize the space pays can be split."))
    if not award.prize.amount_per_winner:
        raise ProgrammeError("prize_amount_required", gettext("Set the prize amount before splitting it."))
    return award.prize.amount_per_winner


def leader_of(snapshot):
    from .payouts import _leader
    return _leader(snapshot)


def has_standing_payout(award):
    from .prize_lineage import standing_payouts
    return standing_payouts(award).exists()


def _validate_rows(award, snapshot, rows):
    total = award_total(award)
    from .prize_precision import require_precision
    for row in rows:
        require_precision("shares", row["amount"], award.prize.event.makerspace)
    members = [row["member_id"] for row in rows]
    if len(set(members)) != len(members) or not set(members) <= set(snapshot.member_ids):
        raise ValidationError({"shares": gettext("Split the prize between members of the winning team, once each.")})
    if sum((Decimal(row["amount"]) for row in rows), Decimal("0")) > total:
        raise ValidationError({"shares": gettext('The shares add up to more than the prize ({total}).').format(total=total)})
    if has_standing_payout(award):
        raise ProgrammeError("payout_exists", gettext("A payout is already recorded for this prize; reverse it first."))
    from .models_prize_money import HackathonPrizeOutcome
    from .prize_lineage import lineage_ids
    if HackathonPrizeOutcome.objects.filter(award_id__in=lineage_ids(award)).exists():
        raise ProgrammeError("already_settled", gettext("This prize has a recorded outcome; its split is fixed."))


def _replace(event, award, rows, *, actor, confirmed_for):
    from .payout_split import lineage_shares
    lineage_shares(award).delete()  # never paid: no payout stands (checked)
    now = timezone.now()
    made = []
    for row in rows:
        confirmed = row["member_id"] in confirmed_for
        made.append(HackathonPrizeShare.objects.create(
            event=event, makerspace=event.makerspace, award=award, member_id=row["member_id"], amount=row["amount"],
            state="confirmed" if confirmed else "proposed", proposed_by=actor, confirmed_at=now if confirmed else None))
    return made


def propose(event_id, award_id, *, actor, data):
    """The winning team's leader proposes the split (member route)."""
    from .payouts import _published_award
    values = validated(SplitInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_claims(event)

        def run():
            award = _published_award(event, award_id)
            snapshot = runtime().snapshot(award.submission_snapshot_id)
            if actor.pk not in snapshot.member_ids:
                raise Http404
            if leader_of(snapshot) != actor.pk:
                raise ProgrammeError("leader_required", gettext("Only the team leader proposes the split."), status=403)
            _validate_rows(award, snapshot, values["shares"])
            shares = _replace(event, award, values["shares"], actor=actor, confirmed_for={actor.pk})
            record(actor, "event.prize.split_proposed", makerspace=event.makerspace, target=award,
                   meta={"event_id": event.pk, "award_id": award.pk, "shares": len(shares)})
            from .prize_notices import prize_step_notice
            for share in shares:  # each other member is asked to confirm their share
                if share.state == "proposed":
                    prize_step_notice(event, share.member_id, "prize_split_proposed", share.pk)
            return award_projection(award)
        return command(event, actor, values, path=f"prize-awards/{award_id}/split", run=run)


def record_split(event_id, award_id, *, actor, data):
    """Staff record a split the team agreed in person: every share is confirmed at once."""
    from .payouts import _published_award, require_recorder
    values = validated(SplitInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)
        require_claims(event)

        def run():
            award = _published_award(event, award_id)
            snapshot = runtime().snapshot(award.submission_snapshot_id)
            _validate_rows(award, snapshot, values["shares"])
            members = {row["member_id"] for row in values["shares"]}
            shares = _replace(event, award, values["shares"], actor=actor, confirmed_for=members)
            record(actor, "event.prize.split_recorded", makerspace=event.makerspace, target=award,
                   meta={"event_id": event.pk, "award_id": award.pk, "shares": len(shares)})
            return award_projection(award)
        return command(event, actor, values, path=f"prize-awards/{award_id}/split", run=run)


def respond(event_id, share_id, *, actor, data, accept):
    """A member confirms or declines their proposed share."""
    values = validated(ShareRespondInput, data)
    with mutation(event_id, actor, owner=True) as (event, _):
        require_claims(event)

        def run():
            share = HackathonPrizeShare.objects.select_for_update().filter(event=event, pk=share_id,
                                                                          member=actor).first()
            if share is None:
                raise Http404
            if share.version != values["expected_version"]:
                raise ProgrammeError("stale_version", gettext("This share changed."), current_version=share.version)
            if share.state != "proposed":
                raise ProgrammeError("invalid_transition", gettext("Only a proposed share can be answered."))
            share.state = "confirmed" if accept else "declined"
            share.confirmed_at = timezone.now() if accept else None
            share.version += 1
            share.save()
            if accept:  # Literal actions, so the audit catalogue labels each one.
                record(actor, "event.prize.share_confirmed", makerspace=event.makerspace, target=share,
                       meta={"event_id": event.pk, "award_id": share.award_id, "share_id": share.pk})
            else:
                record(actor, "event.prize.share_declined", makerspace=event.makerspace, target=share,
                       meta={"event_id": event.pk, "award_id": share.award_id, "share_id": share.pk})
            return award_projection(share.award)
        return command(event, actor, values, path=f"prize-shares/{share_id}/{'confirm' if accept else 'decline'}", run=run)


def share_projection(share):
    return {"id": share.pk, "award_id": share.award_id, "member_id": share.member_id, "amount": share.amount,
            "state": share.state, "version": share.version, "confirmed_at": share.confirmed_at}


def award_projection(award):
    from .payout_split import lineage_shares
    shares = lineage_shares(award).order_by("pk")
    return {"award_id": award.pk, "prize_name": award.prize_name, "total": award.prize.amount_per_winner,
            "shares": [share_projection(row) for row in shares],
            "split_open": not has_standing_payout(award)}
