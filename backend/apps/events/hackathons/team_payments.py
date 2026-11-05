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
    return close_charge(event=team.event, subject_type="team_registration", subject_id=team.pk, actor=actor,
                        reason_code="team_rejected", audit_action="event.team.payment_closed")


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
