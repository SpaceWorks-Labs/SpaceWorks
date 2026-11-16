"""L21b paid teams (C-39): the LEADER PAYS ONCE, one fixed price per team (Q-E1).

- The charge is raised after the team is confirmed (C-34): when a team-together cohort is confirmed,
  or, in the other team modes, when the team's roster locks. It is raised on the leader at that
  moment, once; adding or removing members never re-prices it and never refunds.
- The team is HELD while the leader pays: its project cannot be submitted until the charge is paid
  or waived (`team_payment_settled`).
- A rejected, declined, expired or withdrawn cohort, or a disbanded team, closes the charge: a pending
  one is voided, a paid one opens a refund DUE case for the leader's payment (#59). Never a refund.
There is no per-member mode. With `events.paid_teams` off nothing is charged and nothing is held.
"""

from django.db import transaction

CLOSED_COHORT = ("rejected", "declined", "expired", "withdrawn")


def team_fee(event):
    from apps.events.judging.feature import PAID_TEAMS, enabled
    from apps.events.judging.options import option
    from apps.payments.availability import charge_tracking_enabled
    if not enabled(event.makerspace, PAID_TEAMS) or not charge_tracking_enabled(event.makerspace, "events"):
        return None
    return option(event, "team_fee")


def raise_team_charge(team, actor=None):
    from apps.events.programme_charges import raise_charge
    return raise_charge(event=team.event, subject_type="team_registration", subject_id=team.pk, member=team.leader,
                        amount=team_fee(team.event), actor=actor, audit_action="event.team.payment_raised",
                        target={"type": "team", "id": team.pk, "label": "Team registration"})


def team_payment_settled(team):
    from apps.events.judging.feature import PAID_TEAMS, enabled
    from apps.events.programme_charges import settled_or_free
    if not enabled(team.event.makerspace, PAID_TEAMS):
        return True
    return settled_or_free(team.event, "team_registration", team.pk)


def close_team_charge(team, actor=None):
    from apps.events.programme_charges import close_charge
    # Hack-money G1: a cohort withdrawn because the space cancelled the event is owed for that reason.
    reason = "event_cancelled" if team.event.status == "cancelled" else "team_rejected"
    return close_charge(event=team.event, subject_type="team_registration", subject_id=team.pk, actor=actor,
                        reason_code=reason, audit_action="event.team.payment_closed")


def missing_charges(event):
    """Hack-money G15: teams that owe a team charge that was never raised (a failed signal).

    A team is owed a charge once confirmed: a locked roster outside team-together mode, or a
    confirmed team-together cohort. Disbanded teams and closed cohorts owe nothing.
    """
    from apps.events.programme_charges import find_charge
    from .admission_models import HackathonApplicationCohort
    from .team_models import HackathonTeam
    if not team_fee(event):
        return []
    together = _team_mode_for_event(event.pk) == "team_together"
    confirmed = set(HackathonApplicationCohort.objects.filter(event_id=event.pk, state="confirmed")
                    .values_list("team_id", flat=True))
    teams = HackathonTeam.objects.filter(event_id=event.pk).select_related("leader", "event__makerspace").order_by("pk")
    teams = teams.filter(pk__in=confirmed).exclude(state="disbanded") if together else teams.filter(state="locked")
    return [team for team in teams if find_charge(event, "team_registration", team.pk) is None]


def raise_missing(event, team_id, actor):
    """Staff "raise charge now" (G15): idempotent through `raise_charge`; 404 for a team owing nothing."""
    from django.http import Http404
    from apps.events.programme_charges import find_charge
    from .team_models import HackathonTeam
    if not HackathonTeam.objects.filter(pk=team_id, event_id=event.pk).exists():
        raise Http404
    team = next((row for row in missing_charges(event) if row.pk == team_id), None)
    if team is None:
        existing = find_charge(event, "team_registration", team_id)
        if existing is None:
            raise Http404  # This team owes no charge (not confirmed, disbanded, or no team fee).
        return existing
    return raise_team_charge(team, actor)


def _team_mode_for_event(event_id):
    from .admission_models import HackathonConfig
    return HackathonConfig.objects.filter(event_id=event_id).values_list("team_mode", flat=True).first()


def subject_starts_at(payment):
    """Refund policy reference time for both L21b subjects: the event's start."""
    from apps.events.models import HackathonSubmission, HackathonTeam
    model = HackathonSubmission if payment.subject_type == "submission_fee" else HackathonTeam
    return model.objects.filter(pk=payment.subject_id).values_list("event__starts_at", flat=True).first()


def _team_mode(team):
    from .admission_models import HackathonConfig
    return HackathonConfig.objects.filter(event_id=team.event_id).values_list("team_mode", flat=True).first()


def _team_saved(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    team_id, state = instance.pk, instance.state
    if state == "locked" and _team_mode(instance) == "team_together":
        return  # A team-together cohort is charged when it is CONFIRMED, not when it seals.
    if state not in ("locked", "disbanded"):
        return
    transaction.on_commit(lambda: _apply(team_id, close=state == "disbanded"))


def _cohort_saved(sender, instance, **kwargs):
    if kwargs.get("raw") or not instance.team_id:
        return
    if instance.state == "confirmed":
        transaction.on_commit(lambda: _apply(instance.team_id, close=False))
    elif instance.state in CLOSED_COHORT:
        transaction.on_commit(lambda: _apply(instance.team_id, close=True))


def _apply(team_id, *, close):
    import logging
    from .team_models import HackathonTeam
    team = HackathonTeam.objects.select_related("event__makerspace", "leader").filter(pk=team_id).first()
    if team is None:
        return
    try:
        if close:
            close_team_charge(team)
        else:
            raise_team_charge(team)
    except Exception:  # never fail the team or admission change itself; staff can raise it by hand
        logging.getLogger(__name__).exception("Team charge update failed", extra={"team_id": team_id})


def connect_signals():
    from django.db.models.signals import post_save
    from .admission_models import HackathonApplicationCohort
    from .team_models import HackathonTeam
    post_save.connect(_team_saved, sender=HackathonTeam, dispatch_uid="events.team_payments.team_saved")
    post_save.connect(_cohort_saved, sender=HackathonApplicationCohort, dispatch_uid="events.team_payments.cohort_saved")
