"""G outer endpoints: inline stage/request binding and stage guards on RSVP/check-in."""
import json
from uuid import uuid4
import pytest
from apps.events import services
from apps.events.models import EventRegistration
from apps.events.staged_forms.response_models import StageFormAssignment, StageFormResponseRevision
from apps.payments.event_payouts.errors import PayoutError
from .conftest import definition, payload

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("stage_env", ["ordinary"], indirect=True)
def test_registration_binds_inline_stage_in_the_signup_transaction(stage_env):
    env = stage_env
    row = definition(env, required=True, missed_action="block", blocked_actions=["check_in"])
    registration = services.register(env.event, member=env.owner, actor=env.owner, email="m@example.test", phone="123",
        inline_forms={"operation_id": uuid4(), "stage_forms": [payload(row)]})
    assignment = StageFormAssignment.objects.get(stage_form=row, owner_member=env.owner)
    assert assignment.registration_id == registration.pk and assignment.state == "completed"
    assert StageFormResponseRevision.objects.count() == 1


@pytest.mark.parametrize("stage_env", ["ordinary"], indirect=True)
def test_omitted_required_application_form_refuses_the_whole_signup(stage_env):
    env = stage_env
    definition(env, required=True, missed_action="block", blocked_actions=["check_in"])
    with pytest.raises(PayoutError) as exc:
        services.register(env.event, member=env.owner, actor=env.owner, email="m@example.test", phone="123")
    assert exc.value.detail["code"] == "stage_incomplete"
    assert not EventRegistration.objects.filter(event=env.event).exists()
    assert not StageFormAssignment.objects.exists()


@pytest.mark.parametrize("stage_env", ["ordinary"], indirect=True)
def test_present_request_block_with_module_off_is_refused(stage_env):
    env = stage_env
    with pytest.raises(PayoutError) as exc:
        services.register(env.event, member=env.owner, actor=env.owner,
            inline_forms={"operation_id": uuid4(), "reimbursement_request": {"submit": True}})
    assert exc.value.detail["code"] == "reimbursement_unavailable"
    assert not EventRegistration.objects.filter(event=env.event).exists()


@pytest.mark.parametrize("stage_env", ["ordinary"], indirect=True)
def test_staff_cannot_answer_a_members_inline_forms(stage_env):
    env = stage_env
    with pytest.raises(PayoutError) as exc:
        services.register(env.event, member=env.owner, actor=env.manager, staff_registration=True,
            inline_forms={"operation_id": uuid4(), "stage_forms": []})
    assert exc.value.detail["code"] == "owner_consent_required"


@pytest.mark.parametrize("stage_env", ["ordinary"], indirect=True)
def test_check_in_is_blocked_until_the_required_stage_form_is_complete(stage_env):
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.services_checkin import mark_attended
    env = stage_env
    registration = EventRegistration.objects.create(event=env.event, member=env.owner, name="Maker",
        email="maker@example.test", phone="", registration_audience="accounts", status="registered")
    definition(env, key="pre", stage="pre_event", required=True, missed_action="block", blocked_actions=["check_in"],
               published_at=timezone.now() - timedelta(days=1))
    env.event.starts_at = timezone.now() - timedelta(minutes=5)
    env.event.save(update_fields=["starts_at"])
    with pytest.raises(PayoutError) as exc:
        mark_attended(registration, actor=env.manager)
    assert exc.value.detail["code"] == "stage_incomplete"
    registration.refresh_from_db()
    assert registration.status == "registered"


@pytest.mark.parametrize("stage_env", ["ordinary"], indirect=True)
def test_base_and_stage_forms_cannot_save_conflicting_values(stage_env, monkeypatch):
    from apps.accounts.saved_details import subject_binding
    from apps.accounts.saved_details.errors import SavedDetailsError
    from apps.events.staged_forms import prefill_provider
    env = stage_env
    monkeypatch.setattr(subject_binding, "_provider", prefill_provider)
    question = {"id": "name", "type": "short_text", "label": "Name", "required": True, "profile_field_key": "name"}
    env.event.custom_form = {"schema_version": 2, "form_id": str(uuid4()), "revision": 1, "questions": [question]}
    env.event.save(update_fields=["custom_form"])
    row = definition(env, questions=[question])
    operation = uuid4()
    base = {"form": {k: env.event.custom_form[k] for k in ("schema_version", "form_id", "revision")},
            "answers": {"name": "Maker Base"}, "derivations": {}, "save_choices": {"name": True},
            "saved_detail_versions": {"name": 0}, "operation_id": operation,
            "event_date_revision": env.event.event_date_revision}
    stage = payload(row, answers={"name": "Maker Stage"}, save_choices={"name": True}, saved_detail_versions={"name": 0})
    with pytest.raises(SavedDetailsError) as exc:
        services.register(env.event, member=env.owner, actor=env.owner, email="m@example.test", phone="123",
            form_payload=base, inline_forms={"operation_id": operation, "stage_forms": [stage]})
    assert str(exc.value.detail["code"]) == "saved_detail_form_conflict"
    assert "name" in json.dumps(exc.value.detail, default=str)
    assert not EventRegistration.objects.filter(event=env.event).exists()
