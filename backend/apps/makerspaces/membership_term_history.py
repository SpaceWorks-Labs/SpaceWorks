"""The append-only standing history of membership terms (X7) and its derived view.

`record` is called by every writer that changes a term's standing -- opening, expiry,
cancellation, extension, a refund that ends it -- inside that writer's transaction, and
emits `membership.term_status_changed`. `standing` derives the current standing from the
stored status and dates; it never writes.
"""
from datetime import timedelta

from apps.audit import services as audit
from apps.makerspaces.models_membership_rules import TermStanding
from apps.makerspaces.models_membership_terms import MembershipTerm, MembershipTermStatusEvent


def record(term, status, *, effective_at, actor=None, reason="", ends_at=None):
    membership = term.membership
    row = MembershipTermStatusEvent.objects.create(
        makerspace_id=membership.makerspace_id, membership=membership, term=term, status=status,
        effective_at=effective_at, ends_at=ends_at or term.ends_at, actor=actor, reason=(reason or "")[:500],
    )
    audit.record(actor, "membership.term_status_changed", makerspace=membership.makerspace, target=term,
                 meta={"membership_id": membership.pk, "term_id": term.pk, "status": status,
                       "event_id": row.pk, "effective_at": effective_at.isoformat()})
    return row


def record_opened(term, *, actor=None, now):
    """A future term is UPCOMING from now and ACTIVE from its start; both rows are written
    at opening, so a report can rebuild the standing on any date without a sweep."""
    if term.starts_at > now:
        record(term, TermStanding.UPCOMING, effective_at=now, actor=actor)
    return record(term, TermStanding.ACTIVE, effective_at=term.starts_at, actor=actor)


def record_expiry(term):
    """Expiry is ENDED when a successor continues the membership (effective at the old
    end), LAPSED when none does (effective when grace ran out, with GRACE before it)."""
    followed = MembershipTerm.objects.filter(
        membership_id=term.membership_id, status=MembershipTerm.Status.ACTIVE, starts_at__gte=term.ends_at,
    ).exclude(pk=term.pk).exists()
    if followed:
        return record(term, TermStanding.ENDED, effective_at=term.ends_at)
    lapsed_at = grace_end(term)
    if lapsed_at > term.ends_at:
        record(term, TermStanding.GRACE, effective_at=term.ends_at)
    return record(term, TermStanding.LAPSED, effective_at=max(lapsed_at, term.ends_at))


def grace_end(term):
    from apps.makerspaces.membership_renewals import grace_end as renewal_grace_end
    return renewal_grace_end(term)


def standing(term, now):
    """The derived standing: upcoming / active / grace / ended / lapsed / cancelled."""
    if term.status == MembershipTerm.Status.CANCELLED:
        return TermStanding.CANCELLED
    if term.status == MembershipTerm.Status.ACTIVE:
        if term.starts_at > now:
            return TermStanding.UPCOMING
        if term.ends_at > now:
            return TermStanding.ACTIVE
        return TermStanding.GRACE if grace_end(term) > now else TermStanding.LAPSED
    successor = getattr(term, "_has_successor", None)
    if successor is None:
        successor = MembershipTerm.objects.filter(
            membership_id=term.membership_id, starts_at__gte=term.ends_at - timedelta(seconds=1),
        ).exclude(pk=term.pk).exclude(status=MembershipTerm.Status.CANCELLED).exists()
    return TermStanding.ENDED if successor else TermStanding.LAPSED


def standing_at(events, instant):
    """Rebuild a term's standing at `instant` from its history rows (effective time)."""
    current = None
    for row in sorted(events, key=lambda event: (event.effective_at, event.pk)):
        if row.effective_at > instant:
            break
        if row.status != TermStanding.EXTENDED:
            current = row.status
    return current
