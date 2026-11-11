"""Regression cases found during the independent lane review; run after G registration."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
import pytest
from apps.events.hackathons.admission_cohorts import invalidate_locked, roster_hash
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_models import HackathonApplicationCohort
from apps.events.hackathons.admission_transactions import command
from apps.events.hackathons.admission_workflow import save_application
from apps.events.hackathons.review_models import ApplicationReviewAssignment
from apps.events.hackathons.review_projection import project_assignment, project_review_result
from apps.events.hackathons.review_workflow import submit
from apps.events.hackathons.team_lifecycle import eligibility_changed_locked
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from tests.events.programme.admission.test_support import world, submitted, cmd
from tests.events.programme.admission.test_application_workflow import body

pytestmark = pytest.mark.django_db(transaction=True)


def test_lost_response_replay_skips_preparation_after_offer_lock(world, monkeypatch):
    value = body(world)
    first, status = save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    monkeypatch.setattr(world.forms, "prepare", lambda **kwargs: pytest.fail("replay must not prepare/key provision"))
    replay, replay_status = save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    assert (replay.pk, replay_status) == (first.pk, status)


def test_historical_assignment_cannot_project_resubmitted_answers(world):
    app = submitted(world, state="submitted")
    assignment = ApplicationReviewAssignment.objects.create(event=world.event, application=app, reviewer=world.other)
    app.answers_changed_at = timezone.now() + timedelta(seconds=1)
    app.save(update_fields=["answers_changed_at"])
    with pytest.raises(ProgrammeError) as exc:
        project_assignment(assignment, actor=world.other, config=world.config)
    assert exc.value.status_code == 404


def test_recusal_acknowledgement_and_replay_do_not_read_answers(world):
    app = submitted(world, state="submitted")
    assignment = ApplicationReviewAssignment.objects.create(event=world.event, application=app, reviewer=world.other)
    value = cmd(assignment.version, recusal_code="known_person")
    for _ in range(2):
        row = submit(event_id=world.event.pk, review_id=assignment.pk, actor=world.other, data=value)
        result = project_review_result(row, actor=world.other, config=world.config)
        assert result["state"] == "recused" and result["applications"] == []
        with pytest.raises(ProgrammeError):
            project_assignment(row, actor=world.other, config=world.config)


def team_cohort(world):
    app = submitted(world, state="waitlisted")
    app.answer_locked_at = timezone.now()
    # The team and its active leader commit together (deferred leader guard).
    with transaction.atomic():
        team = HackathonTeam.objects.create(event=world.event, leader=world.owner, name="Sealed", normalized_name="sealed")
        cohort = HackathonApplicationCohort.objects.create(event=world.event, team=team, state="waitlisted")
        app.cohort = cohort
        app.save()
        member = HackathonTeamMember.objects.create(event=world.event, team=team, application=app,
            member=world.owner, creator=world.owner, state="active", joined_at=timezone.now())
    cohort.sealed_roster_hash, cohort.sealed_at = roster_hash([member]), timezone.now()
    cohort.save()
    return app, team, cohort, member


def test_waitlisting_preserves_sealed_roster(world):
    app, team, cohort, member = team_cohort(world)
    with command(event_id=world.event.pk, actor=world.owner, data=cmd(), action="test.waitlist", owner=True) as ctx:
        eligibility_changed_locked(ctx, app)
    member.refresh_from_db(); team.refresh_from_db(); cohort.refresh_from_db()
    assert member.state == "active" and team.leader_id == world.owner.pk
    assert cohort.sealed_roster_hash == roster_hash([member])


def test_roster_invalidation_archives_before_unlocking_answers(world):
    app, team, cohort, _ = team_cohort(world)
    old = app.answers_snapshot
    with command(event_id=world.event.pk, actor=world.owner, data=cmd(), action="test.invalidate", owner=True) as ctx:
        invalidate_locked(ctx, team)
    app.refresh_from_db()
    assert app.state == "draft" and app.answer_locked_at is None
    revision = app.answer_revisions.get()
    assert revision.answers_snapshot == old and revision.locked_at is not None
    with pytest.raises(ValueError):
        revision.save()


def test_submitted_answer_edit_revokes_previous_sharing_consent(world):
    world.config.review_mode = "rolling"
    world.config.optional_mlh_schema = {"revision": 1}
    world.config.save()
    value = body(world)
    value["optional_consents"] = {"mlh_data_sharing": True}
    app, _ = save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    assert app.answer_locked_at is None and app.optional_consents["mlh_data_sharing"]["accepted"]
    value = {**body(world), "expected_version": app.version, "answers": {"work": "revised"},
             "optional_consents": {"mlh_data_sharing": False}}
    app, _ = save_application(event=world.event, actor=world.owner, payload=value, submit=False)
    assert app.state == "submitted" and not app.optional_consents["mlh_data_sharing"]["accepted"]
    assert [transition for _, transition in world.bridge.calls] == ["pending"]


def test_released_review_coverage_ignores_revoked_reviewer(world, monkeypatch):
    from apps.events.hackathons.admission_decisions import require_reviews
    from apps.events.hackathons.review_models import ApplicationDecision, ApplicationReview
    from types import SimpleNamespace
    world.config.review_mode, world.config.review_count = "batch", 1
    app = submitted(world, state="submitted")
    assignment = ApplicationReviewAssignment.objects.create(event=world.event, application=app,
        reviewer=world.other, state="submitted")
    ApplicationReview.objects.create(assignment=assignment, scores={"craft": 3})
    monkeypatch.setattr("apps.events.event_authority.can", lambda *args: False)
    with pytest.raises(ProgrammeError) as exc:
        require_reviews(world.config, app, SimpleNamespace(review_override_code=""))
    assert exc.value.detail["code"] == "review_coverage_required"
