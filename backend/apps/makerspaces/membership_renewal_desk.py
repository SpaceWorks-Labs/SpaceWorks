"""The renewal desk (G16 worklist, X17): who is due, a manual nudge, and extend-by-hand.

Behind `membership.renewal_desk`. Everything here is staff work in ONE space under
`manage_members`; scoping happens in the views through rbac.

* `worklist` lists active memberships whose latest term ends within the window, is in
  grace, or lapsed within the last `LAPSED_DAYS` days and has no successor.
* `send_reminders` nudges the chosen members by their notification channels, at most
  once per member per local day (the notification revision is the day, so a second
  click the same day reuses the same intent). Audited per member.
* `extend` moves the current term's end by a number of days or to a date, with a
  required reason; written to the term history (EXTENDED) and audited.
"""
from django.utils.translation import gettext
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.makerspaces.membership_renewals import grace_end
from apps.makerspaces.membership_term_history import record, standing
from apps.makerspaces.models import MakerspaceMembership, MembershipTerm
from apps.makerspaces.models_membership_rules import TermStanding

LAPSED_DAYS = 60
MAX_REMINDERS = 200


def latest_terms(makerspace, *, now=None, window_days=30):
    """`[(membership, term)]` due for renewal attention, soonest end first."""
    now = now or timezone.now()
    horizon = now + timedelta(days=window_days)
    rows = (MembershipTerm.objects.filter(membership__makerspace=makerspace, membership__status="active")
            .exclude(status=MembershipTerm.Status.CANCELLED)
            .select_related("plan", "membership__user", "membership__makerspace")
            .order_by("membership_id", "-ends_at", "-pk"))
    picked = {}
    for term in rows:
        picked.setdefault(term.membership_id, term)
    due = []
    for term in picked.values():
        if term.is_lifetime or term.ends_at > horizon:
            continue
        if term.ends_at < now - timedelta(days=LAPSED_DAYS) and grace_end(term) < now - timedelta(days=LAPSED_DAYS):
            continue
        due.append(term)
    return sorted(due, key=lambda term: (term.ends_at, term.pk))


def worklist(makerspace, *, now=None, window_days=30):
    now = now or timezone.now()
    reminded = reminded_today(makerspace, now)
    for term in latest_terms(makerspace, now=now, window_days=window_days):
        yield {"membership": term.membership, "term": term, "standing": standing(term, now),
               "grace_ends_at": grace_end(term), "reminded_today": term.membership_id in reminded}


def _day_bounds(makerspace, now):
    """The space's local calendar day containing `now`, and its aware bounds."""
    day = to_local(makerspace, now).date()
    start, end = local_day_bounds(makerspace, day)
    return day, start, end


def reminded_today(makerspace, now):
    from apps.audit.models import AuditLog
    _, start, end = _day_bounds(makerspace, now)
    ids = AuditLog.objects.filter(makerspace=makerspace, action="membership.renewal_reminder_sent",
                                  created_at__gte=start, created_at__lt=end).values_list("target_id", flat=True)
    return {int(value) for value in ids if str(value).isdigit()}


def send_reminders(actor, makerspace, membership_ids, *, now=None):
    """Remind each chosen member once today. Returns {"sent": [...], "skipped": [...]}."""
    now = now or timezone.now()
    ids = list(dict.fromkeys(int(value) for value in membership_ids))[:MAX_REMINDERS]
    due = {term.membership_id: term for term in latest_terms(makerspace, now=now)}
    day, _, _ = _day_bounds(makerspace, now)
    already = reminded_today(makerspace, now)
    sent, skipped = [], []
    from apps.makerspaces.notifications_l4 import notify_renewal_reminder
    for membership_id in ids:
        term = due.get(membership_id)
        if term is None or membership_id in already:
            skipped.append(membership_id)
            continue
        with transaction.atomic():
            notify_renewal_reminder(term, day)
            audit.record(actor, "membership.renewal_reminder_sent", makerspace=makerspace, target=term.membership,
                         meta={"membership_id": membership_id, "term_id": term.pk, "day": day.isoformat()})
        sent.append(membership_id)
    return {"sent": sent, "skipped": skipped}


def extend(actor, membership, *, reason, days=None, until=None):
    """Move the current (or latest) term's end; never a lifetime term."""
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": gettext("Say why this membership is being extended.")})
    if (days is None) == (until is None):
        raise ValidationError({"detail": gettext("Give either a number of days or a new end date.")})
    from apps.makerspaces.membership_features import require_membership_feature_locked
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(membership.makerspace_id)
        makerspace = require_membership_feature_locked(membership.makerspace_id, "renewal_desk")
        membership = MakerspaceMembership.objects.select_for_update().get(pk=membership.pk)
        if membership.status != "active":
            raise ValidationError({"detail": gettext("Only an active membership can be extended.")})
        term = (MembershipTerm.objects.select_for_update().filter(membership=membership, status="active")
                .order_by("-ends_at", "-pk").first())
        if term is None:
            raise ValidationError({"detail": gettext("This membership has no open term to extend.")})
        if term.is_lifetime:
            raise ValidationError({"detail": gettext("A lifetime term never ends.")})
        previous = term.ends_at
        if days is not None:
            if not 1 <= int(days) <= 3650:
                raise ValidationError({"days": gettext("Extend by 1 to 3650 days.")})
            term.ends_at = previous + timedelta(days=int(days))
        else:
            term.ends_at = local_day_bounds(makerspace, until)[1]
            if term.ends_at <= previous:
                raise ValidationError({"until": gettext("The new end must be later than the current end.")})
        term.save(update_fields=["ends_at"])
        term.membership = membership
        record(term, TermStanding.EXTENDED, effective_at=timezone.now(), actor=actor, reason=reason,
               ends_at=term.ends_at)
        audit.record(actor, "membership.extended", makerspace=makerspace, target=term,
                     meta={"membership_id": membership.pk, "term_id": term.pk,
                           "from": previous.isoformat(), "to": term.ends_at.isoformat()})
    return term
