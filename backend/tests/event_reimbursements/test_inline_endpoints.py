"""The request block travels with the real registration and application submit."""
from uuid import uuid4
import pytest
from apps.events.services_registration import register
from apps.events.hackathons.admission_workflow import save_application
from apps.event_reimbursements.models import GrantRequest
from .conftest import cmd
from .helpers import block

pytestmark = pytest.mark.django_db(transaction=True)


def test_registration_submits_the_request_in_the_signup_transaction(world):
    registration = register(world.event, member=world.owner, actor=world.owner,
        inline_forms={"operation_id": uuid4(), "reimbursement_request": block(world)})
    grant = GrantRequest.objects.get(event=world.event, member=world.owner)
    assert grant.registration_id == registration.pk and grant.request_phase == "application"
    assert grant.state == "requested"


def test_invalid_request_block_leaves_no_partial_registration(world):
    from apps.events.models import EventRegistration
    bad = {**block(world), "programme_version": world.programme.version + 7}
    with pytest.raises(Exception):
        register(world.event, member=world.owner, actor=world.owner,
            inline_forms={"operation_id": uuid4(), "reimbursement_request": bad})
    assert not EventRegistration.objects.filter(event=world.event).exists()
    assert not GrantRequest.objects.exists()


def test_application_submit_carries_the_request_and_replays_its_reference(make_world):
    world = make_world(hackathon=True)
    data = cmd(event_date_revision=world.event.event_date_revision,
        form={"schema_version": 2, "form_id": "application", "revision": 1}, answers={}, derivations={},
        save_choices={}, saved_detail_versions={}, coc={"revision": 1, "accepted": True},
        reimbursement_request=block(world))
    app, _ = save_application(event=world.event, actor=world.owner, submit=True, payload=dict(data))
    grant = GrantRequest.objects.get(event=world.event, member=world.owner)
    assert grant.application_id == app.pk and grant.registration_id == app.registration_id
    again, _ = save_application(event=world.event, actor=world.owner, submit=True, payload=dict(data))
    assert again.pk == app.pk and GrantRequest.objects.count() == 1


def test_application_draft_refuses_inline_blocks(make_world):
    world = make_world(hackathon=True)
    from apps.payments.event_payouts.errors import PayoutError
    from rest_framework.exceptions import APIException
    with pytest.raises(APIException) as exc:
        save_application(event=world.event, actor=world.owner, payload=cmd(
            reimbursement_request=block(world)))
    assert "inline_forms_submit_only" in str(exc.value.detail)
