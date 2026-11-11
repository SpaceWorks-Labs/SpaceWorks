"""Hack-money G4 (winner claim flow) and G7 (#181, the winner's PAN), behind `events.prize_claims`.

A winner gives where to be paid on their share: a country/method from the space's accepted payee
templates (the same closed templates and validation as event reimbursement payouts,
`payments/event_payouts/templates.py`) and, optionally, a PAN for prize tax. Both are written to
`HackathonPrizeClaim`, mandatory-encrypted, and read back only masked. A leader with no split gets
a single full-amount share when they claim (the L21b default payee).

The claim window (`prize_claim_days` after the results announcement) is optional; after it staff
may mark an unpaid prize forfeited (`prize_outcomes.forfeit`). Finance verifies details before
paying. A member may remove their details while the share is unpaid. Nothing here moves money.
"""

from django.utils.translation import gettext
import json
from contextlib import contextmanager
from datetime import timedelta

from django.http import Http404
from django.utils import timezone

from apps.audit.services import record
from .boundary import command, mutation
from .errors import ProgrammeError
from .models_prize_money import HackathonPrizeClaim, HackathonPrizeShare
from .ports import runtime
from .prize_shares import award_total, has_standing_payout, leader_of, require_claims
from .prize_tax import clean_pan, mask_pan
from .serializers import CommandInput, validated
from .serializers_prize import PrizeClaimInput


@contextmanager
def claim_key(makerspace_id, *, create=True):
    """Prepare the tenant key OUTSIDE any transaction: a claim's fields are mandatory-encrypted."""
    from apps.encryption.tenant_preparation import holds_tenant_key, prepare_tenant_key, tenant_key_context
    if holds_tenant_key(makerspace_id):
        yield
        return
    with tenant_key_context(prepare_tenant_key(makerspace_id, create=create)):
        yield


def claim_deadline(event):
    from .models_results import ResultPublicationState
    from .options import option
    days = option(event, "prize_claim_days")
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement").first()
    if not days or state is None or state.current_announcement_id is None:
        return None
    return state.current_announcement.published_at + timedelta(days=days)


def _share_for(event, award, actor):
    from .payout_split import lineage_shares
    share = lineage_shares(award).select_for_update().filter(member=actor).first()
    if share is not None:
        return share
    snapshot = runtime().snapshot(award.submission_snapshot_id)
    if lineage_shares(award).exists() or leader_of(snapshot) != actor.pk:
        raise Http404  # a split exists without this member, or only the leader is the default payee
    if has_standing_payout(award):
        raise ProgrammeError("payout_exists", gettext("This prize was already paid."))
    return HackathonPrizeShare.objects.create(event=event, makerspace=event.makerspace, award=award, member=actor,
                                              amount=award_total(award), state="confirmed", proposed_by=actor,
                                              confirmed_at=timezone.now())


def submit(event_id, award_id, *, actor, data):
    from apps.payments.event_payouts.templates import TEMPLATE_VERSION, configured_templates, template_key, validate_details
    from apps.payments.event_payouts.validation import PayoutValidationError
    from .payouts import _published_award
    values = validated(PrizeClaimInput, data)
    pan = clean_pan(values.get("pan", ""))
    event = runtime_event(event_id)
    with claim_key(event.makerspace_id), mutation(event_id, actor, owner=True) as (event, _):
        require_claims(event)

        def run():
            award = _published_award(event, award_id)
            if actor.pk not in runtime().snapshot(award.submission_snapshot_id).member_ids:
                raise Http404
            deadline = claim_deadline(event)
            if deadline is not None and timezone.now() > deadline:
                raise ProgrammeError("claim_window_closed", gettext("The claim window for this prize has closed."))
            share = _share_for(event, award, actor)
            if share.state != "confirmed":
                raise ProgrammeError("share_not_confirmed", gettext("Confirm your share before giving payee details."))
            try:
                key = template_key(values["country"], values["method"])
                enabled, _ = configured_templates(event.makerspace_id)
                details = validate_details(country=values["country"], method=values["method"], template=key,
                                           version=TEMPLATE_VERSION, details=values["details"], enabled_templates=enabled)
            except PayoutValidationError as exc:
                raise ProgrammeError(exc.code, "These payee details are not accepted here.", status=400) from None
            claim = HackathonPrizeClaim.objects.select_for_update().filter(share=share).first() or HackathonPrizeClaim(
                event=event, makerspace=event.makerspace, share=share, version=0)
            claim.country, claim.method, claim.template_key = values["country"], values["method"], key
            claim.details = json.dumps(details, sort_keys=True, separators=(",", ":"))
            claim.pan = pan or claim.pan
            claim.submitted_at, claim.verified_at, claim.verified_by, claim.cleared_at = timezone.now(), None, None, None
            claim.version += 1
            claim.save()
            # Never the details or the PAN: only that a claim was given.
            record(actor, "event.prize.claim_submitted", makerspace=event.makerspace, target=claim,
                   meta={"event_id": event.pk, "award_id": award.pk, "share_id": share.pk})
            return claim_projection(claim)
        return command(event, actor, {**values, "details": "<withheld>", "pan": "<withheld>"},
                       path=f"prize-awards/{award_id}/claim", run=run)


def remove(event_id, award_id, *, actor, data):
    """A member removes their payee details and PAN while their share is unpaid."""
    values = validated(CommandInput, data)
    event = runtime_event(event_id)
    with claim_key(event.makerspace_id), mutation(event_id, actor, owner=True) as (event, _):
        require_claims(event)

        def run():
            from .payouts import _published_award
            from .prize_lineage import lineage_ids
            claim = HackathonPrizeClaim.objects.select_for_update().filter(
                event=event, share__award_id__in=lineage_ids(_published_award(event, award_id)),
                share__member=actor).select_related("share__award").first()
            if claim is None:
                raise Http404
            if has_standing_payout(claim.share.award):
                raise ProgrammeError("payout_exists", gettext("This prize was paid; finance keeps the record."))
            claim.details, claim.pan, claim.cleared_at, claim.verified_at = "", "", timezone.now(), None
            claim.version += 1
            claim.save()
            record(actor, "event.prize.claim_removed", makerspace=event.makerspace, target=claim,
                   meta={"event_id": event.pk, "share_id": claim.share_id})
            return claim_projection(claim)
        return command(event, actor, values, path=f"prize-awards/{award_id}/claim/remove", run=run)


def verify(event_id, share_id, *, actor, data):
    """Finance confirms the payee details are usable (record_payment or the Event Manager)."""
    from .payouts import require_recorder
    values = validated(CommandInput, data)
    event = runtime_event(event_id)
    with claim_key(event.makerspace_id, create=False), mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)
        require_claims(event)

        def run():
            claim = HackathonPrizeClaim.objects.select_for_update().select_related("share").filter(
                event=event, share_id=share_id).first()
            if claim is None or not claim.submitted_at or claim.cleared_at:
                raise Http404
            if claim.version != values["expected_version"]:
                raise ProgrammeError("stale_version", gettext("These details changed."), current_version=claim.version)
            claim.verified_at, claim.verified_by = timezone.now(), actor
            claim.version += 1
            claim.save()
            record(actor, "event.prize.claim_verified", makerspace=event.makerspace, target=claim,
                   meta={"event_id": event.pk, "share_id": share_id})
            from .prize_notices import prize_step_notice
            prize_step_notice(event, claim.share.member_id, "prize_claim_verified", claim.pk)
            return claim_projection(claim)
        return command(event, actor, values, path=f"prize-shares/{share_id}/verify", run=run)


def reveal(event_id, share_id, *, actor, data):
    """Finance reads one winner's full payee details and PAN to pay them (and to deduct tax, #181).
    Every release is re-authorised and audited with its reason, never with the values."""
    from .payouts import require_recorder
    from .serializers_prize import RevealInput
    values = validated(RevealInput, data)
    event = runtime_event(event_id)
    with claim_key(event.makerspace_id, create=False), mutation(event_id, actor, owner=True) as (event, _):
        require_recorder(actor, event)
        require_claims(event)
        claim = HackathonPrizeClaim.objects.filter(event=event, share_id=share_id).first()
        if claim is None or not claim.submitted_at or claim.cleared_at:
            raise Http404
        if claim.version != values["expected_version"]:
            raise ProgrammeError("stale_version", gettext("These details changed."), current_version=claim.version)
        record(actor, "event.prize.claim_revealed", makerspace=event.makerspace, target=claim,
               meta={"event_id": event.pk, "share_id": share_id, "reason_code": values["reason_code"]})
        return {"share_id": share_id, "country": claim.country, "method": claim.method,
                "details": json.loads(claim.details or "{}"), "pan": claim.pan}


def clear_locked(share, *, pan=False):
    """After payment the routing details are no longer needed; after a forfeit nothing is. The PAN of a
    paid share stays (masked) for the space's own tax records. Needs the tenant key; without it the
    claim is left for the purge."""
    from apps.encryption.tenant_preparation import holds_tenant_key
    claim = HackathonPrizeClaim.objects.select_for_update().filter(share=share).first()
    if claim is None or claim.cleared_at or not holds_tenant_key(claim.makerspace_id):
        return
    claim.details, claim.cleared_at = "", timezone.now()
    if pan:
        claim.pan = ""
    claim.version += 1
    claim.save()


def runtime_event(event_id):
    from apps.events.models import Event
    event = Event.objects.filter(pk=event_id).only("pk", "makerspace_id").first()
    if event is None:
        raise Http404
    return event


def claim_projection(claim):
    """Masked only. Call with the tenant key prepared; without it the details show as 'on file'."""
    from apps.payments.event_payouts.templates import masked_details
    on_file = bool(claim and claim.submitted_at and not claim.cleared_at)
    masked, pan = "", ""
    if on_file:
        try:
            masked = masked_details(json.loads(claim.details), country=claim.country, method=claim.method)
            pan = mask_pan(claim.pan)
        except Exception:  # no key in this request: never fall back to plaintext
            masked, pan = "On file", ("On file" if claim.pan else "")
    return {"share_id": claim.share_id if claim else None, "version": claim.version if claim else 0,
            "state": ("verified" if claim.verified_at else "submitted") if on_file else "not_given",
            "country": claim.country if on_file else "", "method": claim.method if on_file else "",
            "masked_details": masked, "pan_masked": pan, "verified": bool(on_file and claim.verified_at)}
