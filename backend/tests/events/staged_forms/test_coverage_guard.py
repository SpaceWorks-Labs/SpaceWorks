"""Actual definitions/assignments, including the absent-worker coverage hole."""
from datetime import timedelta
import pytest
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from apps.events.models import Event, EventRegistration
from apps.events.programme.form_models import EventFormRevision
from apps.events.staged_forms.definition_models import EventStageForm
from apps.events.staged_forms.response_models import StageFormAssignment, StageFormResponse, StageFormResponseRevision
from apps.events.staged_forms.trigger_service import Participant
from apps.events.staged_forms.guards import require_complete_locked, readiness
from apps.payments.event_payouts.errors import PayoutError


@pytest.fixture
def subject(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    now = timezone.now()
    space = Makerspace.objects.create(name="Stage guard", slug="stage-guard")
    member = User.objects.create_user(username="stage-participant", account_kind="member")
    event = Event.objects.create(makerspace=space, title="Ordinary event", starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=3), registration_audience="accounts")
    definition = EventStageForm.objects.create(event=event, slug="follow-up", title="Follow-up", stage="application",
        state="published", published_at=now - timedelta(days=1), required=True, missed_action="block",
        blocked_actions=["claim_submit"], due_after_seconds=3600)
    revision = EventFormRevision.objects.create(event=event, form_key="stage", selector_kind="stage",
        selector_id=definition.pk, revision=1, schema={"schema_version": 2, "form_id": str(definition.form_id), "revision": 1, "questions": []})
    definition.current_revision = revision
    definition.save(update_fields=["current_revision"])
    registration = EventRegistration.objects.create(event=event, member=member, name="Participant", email="stage@example.test", phone="",
        registration_audience="accounts")
    return Participant(event, member.pk, registration), definition


@pytest.mark.django_db
def test_published_blocking_definition_refuses_when_worker_created_nothing(subject):
    participant, definition = subject
    with pytest.raises(PayoutError) as caught, transaction.atomic():
        Event.objects.select_for_update().get(pk=participant.event.pk)
        require_complete_locked(participant, "claim_submit")
    assert str(caught.value.detail["code"]) == "stage_incomplete"
    assert readiness(participant, "claim_submit")["stage_form_ids"] == [definition.pk]
    assert not StageFormAssignment.objects.exists()
    assert participant.registration.status == "registered"


@pytest.mark.django_db
def test_only_exact_pinned_submitted_revision_completes_requirement(subject):
    participant, definition = subject
    now = timezone.now()
    assignment = StageFormAssignment.objects.create(stage_form=definition, event=participant.event,
        owner_member_id=participant.owner_member_id, registration=participant.registration,
        trigger_key="application", trigger_revision=1, pinned_form_revision=definition.current_revision,
        triggered_at=now, opens_at=now, base_due_at=now + timedelta(hours=1), effective_due_at=now + timedelta(hours=1), state="open")
    response = StageFormResponse.objects.create(assignment=assignment, event=participant.event,
        owner_member_id=participant.owner_member_id, form_revision=definition.current_revision)
    assert not readiness(participant, "claim_submit")["ready"]
    revision = StageFormResponseRevision.objects.create(response=response, revision=1,
        form_revision=definition.current_revision, answers_snapshot='{"answers":[]}', submitted_at=now,
        submitted_by_id=participant.owner_member_id, date_revision=1)
    response.current_submitted_revision, response.state = revision, "submitted"
    response.save()
    assignment.completed_response, assignment.state = response, "completed"
    assignment.save()
    assert readiness(participant, "claim_submit")["ready"]
    definition.state = "retired"
    definition.save(update_fields=["state"])
    assert readiness(participant, "claim_submit")["ready"]
    assignment.state, assignment.completed_response = "open", None
    assignment.save()
    assert not readiness(participant, "claim_submit")["ready"]
