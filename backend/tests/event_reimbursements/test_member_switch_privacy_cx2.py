"""Owner standing conceals private events before either module switch is disclosed."""
import pytest
from django.apps import apps
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events.models import Event, EventCommandReceipt, EventRegistration, HackathonApplication
from apps.events.services_registration import register
from apps.event_reimbursements.views_member import (
    AwardAcceptView, AwardDeclineView, ClaimAppealView, ClaimSubmitView, ClaimView,
    ReimbursementView, RequestSubmitView, RequestWithdrawView,
)
from apps.makerspaces.models import Makerspace
from tests.accounts.test_reauthentication import request as session_request
from .conftest import cmd

pytestmark = pytest.mark.django_db(transaction=True)
OWNER_OPERATIONS = (
    (ReimbursementView, "GET"), (ReimbursementView, "POST"),
    (RequestSubmitView, "POST"), (RequestWithdrawView, "POST"),
    (AwardAcceptView, "POST"), (AwardDeclineView, "POST"),
    (ClaimView, "GET"), (ClaimView, "PUT"),
    (ClaimSubmitView, "POST"), (ClaimAppealView, "POST"),
)


def domain_rows():
    models = (*apps.get_app_config("event_reimbursements").get_models(),
              Event, EventRegistration, HackathonApplication, EventCommandReceipt)
    return {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}


def call(world, actor, view, method, *, event_id=None, data=None, origin="http://localhost:5000"):
    session = session_request(actor, surface="member")
    data = cmd() if data is None else data
    req = getattr(APIRequestFactory(), method.lower())(
        "/", data, format="json", HTTP_ORIGIN=origin,
        HTTP_IDEMPOTENCY_KEY=str(data["operation_id"]),
    )
    force_authenticate(req, user=actor, token=session.auth)
    return view.as_view()(req, pk=world.event.pk if event_id is None else event_id,
                          makerspace_id=world.space.pk)


def private_participant(world):
    world.event.is_public = False
    world.event.save(update_fields=["is_public"])
    return register(world.event, member=world.owner, actor=world.manager, staff_registration=True)


@pytest.mark.parametrize("disabled", [None, "events", "event_reimbursements"])
def test_unrelated_person_cannot_distinguish_private_event_from_missing_on_any_owner_operation(world, disabled):
    private_participant(world)
    created = call(world, world.owner, ReimbursementView, "POST")
    assert (created.status_code, created.data.get("code")) == (201, None), created.data
    outsider = User.objects.create_user(username="private-event-outsider", account_kind="member")
    assert outsider.is_active and outsider.access_status == User.AccessStatus.ACTIVE
    assert not EventRegistration.objects.filter(event=world.event, member=outsider).exists()
    missing = world.event.pk + 1000000
    assert not Event.objects.filter(pk=missing).exists()
    if disabled:
        world.space.enabled_modules = [key for key in world.space.enabled_modules if key != disabled]
        world.space.save(update_fields=["enabled_modules"])
    before, audits = domain_rows(), AuditLog.objects.count()
    for view, method in OWNER_OPERATIONS:
        observed, bodies = [], []
        for event_id in (world.event.pk, missing):
            response = call(world, outsider, view, method, event_id=event_id)
            observed.append((response.status_code, response.data["code"]))
            bodies.append(response.data)
            assert observed[-1] == (404, "not_found"), response.data
            assert "module" not in response.data and "feature" not in response.data
            assert domain_rows() == before
            assert AuditLog.objects.count() == audits
        assert observed == [(404, "not_found"), (404, "not_found")]
        assert bodies[0] == bodies[1]


@pytest.mark.parametrize("disabled", [None, "events", "event_reimbursements"])
def test_participant_from_unrelated_origin_is_concealed_before_module_switches(world, disabled):
    private_participant(world)
    foreign = Makerspace.objects.create(name="Unrelated origin", slug="unrelated-origin",
        frontend_domain="unrelated-origin.example.test", frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    if disabled:
        world.space.enabled_modules = [key for key in world.space.enabled_modules if key != disabled]
        world.space.save(update_fields=["enabled_modules"])
    before, audits = domain_rows(), AuditLog.objects.count()
    for view, method in OWNER_OPERATIONS:
        bodies = []
        for event_id in (world.event.pk, world.event.pk + 1000000):
            response = call(world, world.owner, view, method, event_id=event_id,
                            origin="https://" + foreign.frontend_domain)
            bodies.append(response.data)
            assert (response.status_code, response.data["code"]) == (404, "not_found"), response.data
            assert "module" not in response.data
            assert domain_rows() == before
            assert AuditLog.objects.count() == audits
        assert bodies[0] == bodies[1]


@pytest.mark.parametrize("disabled", ["events", "event_reimbursements"])
def test_authorized_participant_gets_typed_off_and_retained_read_and_command_replay_after_restore(world, disabled):
    registration = private_participant(world)
    data = cmd()
    created = call(world, world.owner, ReimbursementView, "POST", data=data)
    assert (created.status_code, created.data.get("code")) == (201, None), created.data
    baseline = call(world, world.owner, ReimbursementView, "GET")
    assert (baseline.status_code, baseline.data.get("code")) == (200, None), baseline.data
    assert baseline.data["available"] is True
    assert baseline.data["request"]["id"] == created.data["id"]
    assert baseline.data["request"]["state"] == "draft"
    assert registration.member_id == world.owner.pk
    original = list(world.space.enabled_modules)
    world.space.enabled_modules = [key for key in original if key != disabled]
    world.space.save(update_fields=["enabled_modules"])
    before, audits = domain_rows(), AuditLog.objects.count()
    for view, method in OWNER_OPERATIONS:
        response = call(world, world.owner, view, method, data=data)
        assert (response.status_code, response.data["code"], response.data["module"]) == (
            404, "module_disabled", disabled,
        ), response.data
        assert domain_rows() == before
        assert AuditLog.objects.count() == audits
    world.space.enabled_modules = original
    world.space.save(update_fields=["enabled_modules"])
    restored = call(world, world.owner, ReimbursementView, "GET")
    assert (restored.status_code, restored.data.get("code")) == (200, None), restored.data
    assert restored.data == baseline.data
    replay = call(world, world.owner, ReimbursementView, "POST", data=data)
    assert (replay.status_code, replay.data.get("code")) == (201, None), replay.data
    assert replay.data == created.data
    assert domain_rows() == before
    assert AuditLog.objects.count() == audits

