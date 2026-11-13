"""Hack-money G6/G8 reads: My prizes, staff claim list, public prize pool, per-event prize pool.

- "My prizes" (member, `events.prize_claims`): every award of a PUBLISHED result whose winning
  snapshot sealed this member, with its status, the member's share, payout (gross, tax, net) and
  claim (masked).
- The public prize list needs the per-event "show prize amounts publicly" switch (off by default)
  and never names a winner, a payee or an amount paid.
- The prize pool (staff, G8): cash announced, sponsorship earmarked to the pool and paid, paid gross,
  tax recorded, owed and recovered. A sponsor_direct prize is counted, never as money the space paid.
"""

from decimal import Decimal

from django.db.models import Sum
from django.http import Http404
from django.utils import timezone

from .models_payouts import HackathonPrizePayout
from .models_prize_money import HackathonPrizeClaim, HackathonPrizeOutcome, HackathonPrizeShare
from .models_results import EventAward, ResultPublicationState
from .ports import runtime

ZERO = Decimal("0.00")


def current_awards(event):
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement").first()
    if state is None or state.current_announcement_id is None:
        return EventAward.objects.none()
    return EventAward.objects.select_related("prize").filter(result_id=state.current_announcement.result_id)


def my_prizes(actor, makerspace_id):
    from apps.events.models import Event, SubmissionSnapshot
    from apps.makerspaces.platform import feature_enabled
    from .options import currency
    from .payout_split import award_status
    from .prize_claims import claim_deadline, claim_projection
    from .prize_shares import leader_of
    from .prize_tax import tax_settings
    from apps.payments.event_payouts.templates import template_descriptors
    snapshots = SubmissionSnapshot.objects.filter(sealed_member_ids__contains=[actor.pk],
                                                  submission__event__makerspace_id=makerspace_id).values("pk")
    rows = []
    events = Event.objects.select_related("makerspace").filter(makerspace_id=makerspace_id)
    for award in EventAward.objects.select_related("prize", "result").filter(
            submission_snapshot_id__in=snapshots).order_by("-pk"):
        event = events.filter(pk=award.prize.event_id).first()
        if event is None or not feature_enabled(event.makerspace, "events.prize_claims"):
            continue
        if not current_awards(event).filter(pk=award.pk).exists():
            continue  # only the published result counts
        from .payout_split import lineage_shares
        from .prize_lineage import standing_payouts
        share = lineage_shares(award).filter(member=actor).first()
        payout = standing_payouts(award).filter(recipient=actor).first()
        claim = HackathonPrizeClaim.objects.filter(share=share).first() if share else None
        is_leader = leader_of(runtime().snapshot(award.submission_snapshot_id)) == actor.pk
        actions = []
        if payout is None and award.prize.kind == "cash" and award.prize.funding == "space":
            if share is None and is_leader and not lineage_shares(award).exists():
                actions += ["propose_split", "claim"]
            if share is not None and share.state == "proposed":
                actions += ["confirm_share", "decline_share"]
            if share is not None and share.state == "confirmed":
                actions += ["claim"] + (["remove_claim"] if claim and claim.submitted_at and not claim.cleared_at else [])
            deadline = claim_deadline(event)
            if deadline is not None and timezone.now() > deadline:
                actions = [a for a in actions if a not in ("claim", "propose_split")]  # the window has closed
        rows.append({"award_id": award.pk, "event_id": event.pk, "event_title": event.title,
                     "prize_name": award.prize_name, "rank": award.rank, "kind": award.prize.kind,
                     "value_text": award.prize.value_text, "status": award_status(award),
                     "currency": currency(event.makerspace),
                     "my_share": _share(share), "my_payout": _payout(payout),
                     "claim": claim_projection(claim) if claim else None, "claim_deadline": claim_deadline(event),
                     "is_leader": is_leader, "allowed_actions": actions,
                     "tax_id_requested": tax_settings(event.makerspace).prize_tds_enabled,
                     "payee_templates": template_descriptors(makerspace_id) if "claim" in actions else []})
    return rows


def _share(share):
    from .prize_shares import share_projection
    return share_projection(share) if share else None


def _payout(payout):
    if payout is None:
        return None
    net = payout.net_amount if payout.net_amount is not None else payout.amount - payout.tds_amount
    return {"gross": str(payout.amount), "tds": str(payout.tds_amount), "net": str(net), "currency": payout.currency,
            "paid_on": payout.paid_on.isoformat()}


def staff_claims(event):
    from .prize_claims import claim_projection
    rows = []
    for share in HackathonPrizeShare.objects.filter(event=event).order_by("award_id", "pk"):
        claim = HackathonPrizeClaim.objects.filter(share=share).first()
        value = claim_projection(claim) if claim else {"share_id": share.pk, "version": 0, "state": "not_given",
            "country": "", "method": "", "masked_details": "", "pan_masked": "", "verified": False}
        rows.append({**value, "share_id": share.pk, "award_id": share.award_id, "member_id": share.member_id,
                     "amount": share.amount, "share_state": share.state})
    return rows


def public_prizes(event):
    from .models_definitions import HackathonPrize
    from .options import currency, option
    if not option(event, "show_prize_amounts"):
        raise Http404
    money = currency(event.makerspace)
    rows = HackathonPrize.objects.filter(event=event).select_related("track", "sponsor").order_by("order", "pk")
    return [{"name": row.name, "track": row.track.name if row.track_id else "",
             "sponsor": row.sponsor.label if row.sponsor_id else "", "kind": row.kind,
             "value_text": row.value_text, "amount_per_winner": row.amount_per_winner if row.kind == "cash" else None,
             "award_count": row.award_count, "currency": money} for row in rows]


def prize_pool(event):
    from apps.payments.models import Payment, SponsorshipCharge
    from .models_definitions import HackathonPrize
    from .options import currency
    cash = HackathonPrize.objects.filter(event=event, kind="cash", funding="space", amount_per_winner__isnull=False)
    announced = sum((row.amount_per_winner * row.award_count for row in cash), ZERO)
    earmarked = SponsorshipCharge.objects.filter(makerspace=event.makerspace, event=event, earmark="prize_pool")
    funded = Payment.objects.filter(makerspace=event.makerspace, subject_type="sponsorship",
                                    subject_id__in=earmarked.values("pk"),
                                    status__in=("paid_online", "paid_offline")).aggregate(total=Sum("amount"))["total"]
    standing = HackathonPrizePayout.objects.filter(event=event, kind="payout", reversal__isnull=True)
    totals = standing.aggregate(gross=Sum("amount"), tds=Sum("tds_amount"))
    owed = ZERO
    from .payout_split import owed_amount
    for award in current_awards(event):
        if award.prize.kind == "cash" and award.prize.funding == "space":
            owed += owed_amount(award)  # part-paid prizes still owe their unpaid shares
    from .peoples_choice_money import owed as peoples_choice_owed
    owed += peoples_choice_owed(event)  # #181: a People's choice cash prize is owed like a judged one.
    recovered = HackathonPrizeOutcome.objects.filter(event=event, kind="recovery_repaid").aggregate(
        total=Sum("amount"))["total"]
    return {"currency": currency(event.makerspace), "announced_total": announced, "sponsor_funded": funded or ZERO,
            "paid_gross": totals["gross"] or ZERO, "tds_recorded": totals["tds"] or ZERO, "owed": owed,
            "recovered": recovered or ZERO,
            "sponsor_direct_awards": current_awards(event).filter(prize__funding="sponsor_direct").count()}
