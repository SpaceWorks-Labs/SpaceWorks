from uuid import uuid4
import pytest
from apps.events.models import EventRegistration
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.hackathons.admission_workflow import save_application
from apps.events.hackathons.admission_ports import ports
from tests.events.programme.admission.test_support import world, cmd

pytestmark = pytest.mark.django_db


def body(world):
    return cmd(0, event_date_revision=world.event.event_date_revision,
        form={"schema_version": 2, "form_id": "application", "revision": 1}, answers={},
        save_choices={}, saved_detail_versions={}, derivations={}, coc={"revision": 1, "accepted": True})


def test_first_submit_pending_then_offer_never_charges_or_confirms(world, monkeypatch):
    # Admission commands now run inside the shared write boundary: record its real
    # fences and its locked-event authority step to keep the lock-order assertion.
    from contextlib import contextmanager
    from apps.events import services_write_boundary as boundary
    real_fences, real_authority = boundary.fences, boundary.lock_authority
    @contextmanager
    def fences(**kwargs):
        world.order.append("fences")
        with real_fences(**kwargs):
            yield
    def lock_authority(*args, **kwargs):
        world.order.append("event")
        return real_authority(*args, **kwargs)
    monkeypatch.setattr(boundary, "fences", fences)
    monkeypatch.setattr(boundary, "lock_authority", lock_authority)
    value = body(world)
    app, status = save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    assert status == 201 and app.state == "offered"
    assert app.registration.status == "pending_approval"
    assert [call[1] for call in world.bridge.calls] == ["pending", "offer"]
    assert app.rsvp_due_at > app.offered_at
    from datetime import timedelta
    assert app.rsvp_due_at - app.offered_at == timedelta(days=4)
    assert world.order.index("fences") < world.order.index("event")
    again, replay_status = save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    assert again.pk == app.pk and replay_status == 201
    assert EventRegistration.objects.filter(event=world.event).count() == 1
    assert len(world.bridge.calls) == 2


def test_coc_failure_rolls_back_application_receipt_and_registration(world):
    value = body(world)
    value["coc"]["accepted"] = False
    with pytest.raises(ProgrammeError) as exc:
        save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    assert exc.value.detail["code"] == "coc_required"
    assert not HackathonApplication.objects.filter(event=world.event).exists()
    assert not EventRegistration.objects.filter(event=world.event).exists()
    from django.apps import apps
    assert not apps.get_model("events", "EventCommandReceipt").objects.filter(event=world.event).exists()


def test_failed_prepared_intent_rolls_back_the_whole_submission(world, monkeypatch):
    monkeypatch.setattr(world.forms, "attach_locked", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("key epoch changed")))
    with pytest.raises(RuntimeError):
        save_application(event=world.event, actor=world.owner, payload=body(world), submit=True)
    assert not HackathonApplication.objects.filter(event=world.event).exists()


def test_changed_operation_body_cannot_reuse_receipt(world):
    value = body(world)
    save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    value["answers"] = {"new": "different"}
    with pytest.raises(ProgrammeError) as exc:
        save_application(event=world.event, actor=world.owner, payload=value, submit=True)
    assert exc.value.detail["code"] == "idempotency_conflict"
