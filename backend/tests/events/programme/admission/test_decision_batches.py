import pytest
from apps.events.hackathons.admission_decisions import stage, finish_batch
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.hackathons.review_models import ApplicationDecisionBatch, ApplicationDecision
from tests.events.programme.admission.test_support import world, submitted, cmd

pytestmark = pytest.mark.django_db


def test_private_stage_does_not_change_application_registration_or_send_notice(world):
    app = submitted(world, state="submitted")
    batch = stage(event_id=world.event.pk, actor=world.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "offer", "reason_code": "review_complete"}]))
    app.refresh_from_db()
    assert app.state == "submitted" and app.registration.status == "pending_approval"
    assert world.notices == [] and world.bridge.calls == []
    finish_batch(event_id=world.event.pk, actor=world.owner, data=cmd(batch.version, batch_id=batch.pk))
    app.refresh_from_db()
    assert app.state == "offered" and len(world.notices) == 1


def test_batch_release_is_all_or_nothing_if_total_offers_do_not_fit(world):
    first, second = submitted(world, state="submitted"), submitted(world, world.other, state="submitted")
    world.config.offer_capacity = 1
    world.config.save()
    batch = stage(event_id=world.event.pk, actor=world.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "offer", "reason_code": "review_complete"}
        for app in (first, second)]))
    with pytest.raises(ProgrammeError) as exc:
        finish_batch(event_id=world.event.pk, actor=world.owner, data=cmd(batch.version, batch_id=batch.pk))
    assert exc.value.detail["code"] == "capacity_full"
    assert set(HackathonApplication.objects.filter(event=world.event).values_list("state", flat=True)) == {"submitted"}
    batch.refresh_from_db()
    assert batch.state == "draft"
    assert not batch.decisions.filter(active_draft=False).exists()


def test_n_reviews_required_unless_explicit_audited_override(world):
    world.config.review_mode = "batch"
    world.config.save()
    app = submitted(world, state="submitted")
    batch = stage(event_id=world.event.pk, actor=world.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "offer", "reason_code": "review_complete"}]))
    with pytest.raises(ProgrammeError) as exc:
        finish_batch(event_id=world.event.pk, actor=world.owner, data=cmd(batch.version, batch_id=batch.pk))
    assert exc.value.detail["code"] == "review_coverage_required"


def test_cancelling_private_batch_sends_nothing(world):
    app = submitted(world, state="submitted")
    batch = stage(event_id=world.event.pk, actor=world.owner, data=cmd(0, decisions=[{
        "application_id": app.pk, "expected_version": app.version, "outcome": "reject", "reason_code": "review_complete"}]))
    finish_batch(event_id=world.event.pk, actor=world.owner, data=cmd(batch.version, batch_id=batch.pk), cancel=True)
    app.refresh_from_db()
    assert app.state == "submitted" and not world.notices
