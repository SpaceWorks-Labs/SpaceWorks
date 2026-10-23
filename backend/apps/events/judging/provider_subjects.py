"""Canonical A/C owner, conflict and award-subject adapters."""

from django.http import Http404

from apps.accounts.models import User
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.models_registration import EventRegistration
from .models_results import EventAward, ResultPublicationState


class ProgrammeSubjects:
    def owner_subject(self, *, event_id, member_id):
        from .boundary import active_member
        actor = User.objects.filter(pk=member_id).first()
        active_member(actor)
        app = HackathonApplication.objects.filter(event_id=event_id, member_id=member_id).exclude(
            state__in=("rejected", "declined", "expired", "withdrawn")).first()
        if app:
            return AnswerSubject(event_id=event_id, owner_member_id=member_id,
                                 kind=SubjectKind.APPLICATION, subject_id=app.pk)
        role = EventRoleAssignment.objects.filter(event_id=event_id, member_id=member_id,
            role__in=("volunteer", "mentor"), imported_inert=False,
            state__in=("draft", "proposed", "applied", "approved", "completed")).order_by("pk").first()
        if role:
            return AnswerSubject(event_id=event_id, owner_member_id=member_id,
                                 kind=SubjectKind.ROLE_ASSIGNMENT, subject_id=role.pk)
        raise Http404

    def require_subject_owner(self, *, actor_id, subject):
        if not isinstance(subject, AnswerSubject) or subject.owner_member_id != actor_id or not subject.subject_id:
            raise Http404
        model, filters = {
            SubjectKind.APPLICATION: (HackathonApplication, {"state__in": ("draft", "submitted", "offered", "waitlisted", "confirmed")}),
            SubjectKind.ROLE_ASSIGNMENT: (EventRoleAssignment, {"imported_inert": False,
                "role__in": ("volunteer", "mentor"), "state__in": ("draft", "proposed", "applied", "approved", "completed")}),
            SubjectKind.REGISTRATION: (EventRegistration, {"status__in": ("registered", "attended")}),
        }[subject.kind]
        if not model.objects.filter(pk=subject.subject_id, event_id=subject.event_id,
                                    member_id=actor_id, **filters).exists():
            raise Http404
        self.owner_subject(event_id=subject.event_id, member_id=actor_id)

    def lock_team(self, *, event_id, team_id, locks):
        self.assert_lock_context(locks)
        if event_id != locks.event_id or not HackathonTeam.objects.select_for_update().filter(
                event_id=event_id, pk=team_id).exists():
            raise Http404

    def require_team_member(self, *, event_id, team_id, member_id, sealed_member_ids, leader=False):
        from .boundary import active_member
        actor = User.objects.filter(pk=member_id).first()
        active_member(actor)
        rows = HackathonTeam.objects.filter(pk=team_id, event_id=event_id).exclude(state="disbanded")
        if leader:
            rows = rows.filter(leader_id=member_id)
        if member_id not in sealed_member_ids or not rows.exists() or not HackathonTeamMember.objects.filter(
                event_id=event_id, team_id=team_id, member_id=member_id, state="active").exists():
            raise Http404

    def is_conflicted(self, *, member_id, team_id, round_id):
        from apps.events.mentoring.policy import is_conflicted
        from .models_definitions import JudgingRound
        if not JudgingRound.objects.filter(pk=round_id, event_id__in=HackathonTeam.objects.filter(
                pk=team_id).values("event_id")).exists():
            raise Http404
        return is_conflicted(member_id=member_id, team_id=team_id, round_id=round_id)


def award_eligible(*, event_id, member_id, award_id, result_revision_id, kind):
    """E requires current published results and the exact sealed winning roster."""
    from .ports import runtime
    if kind == "participant":
        return award_id is None and result_revision_id is None and any(
            s.current and s.eligible and member_id in s.member_ids for s in runtime().snapshots(event_id))
    if kind not in ("winner", "finalist") or not award_id or not result_revision_id:
        return False
    publication = ResultPublicationState.objects.filter(event_id=event_id,
        current_announcement__result_id=result_revision_id).first()
    if publication is None:
        return False
    # E's award FK names a prize; D's immutable EventAward names its winner.
    awards = EventAward.objects.filter(prize_id=award_id, result_id=result_revision_id, result__event_id=event_id)
    if kind == "winner":
        awards = awards.filter(rank=1)
    for award in awards:
        snapshot = runtime().snapshot(award.submission_snapshot_id)
        if snapshot.event_id == event_id and snapshot.current and snapshot.eligible and member_id in snapshot.member_ids:
            return True
    return False
