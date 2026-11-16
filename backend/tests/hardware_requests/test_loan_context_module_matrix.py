"""Contextual lending on/off matrix (owner decision 214e): one scenario table, every surface.

Events off, Bookings off, the lending capability off, the request-workflow module off, combinations and
re-enable. In every scenario the stored history survives; contextual creation and the subject drill-downs
disappear exactly when one of their own switches is off; settlement stays reachable because the payments
ledger is core. Return stays reachable while the request workflow is on. Nothing here weakens a disable guard:
the switches are flipped the way the module tests do, on the space row.
"""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.bookings.models_loan_context import BookingLoanContext
from apps.events.models import EventRegistration
from apps.events.models_loan_context import EventLoanContext
from apps.evidence.storage import EvidenceValidationResult
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest
from apps.operations.reports_loan_context import build_loan_purpose_summary
from apps.operations.reports_loan_context_details import build_booking_equipment, build_event_equipment
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for, make_member
from tests.events.ticketing_helpers import account
from tests.operations.test_loan_context_reports import setup_reports
from tests.return_helpers import make_issued_request, return_payload, make_return_evidence, settlement_payload

pytestmark = pytest.mark.django_db(transaction=True)

# (scenario id, modules switched off, features switched off)
SCENARIOS = [
    ("all_on", (), ()),
    ("events_off", ("events",), ()),
    ("bookings_off", ("bookings",), ()),
    ("events_and_bookings_off", ("events", "bookings"), ()),
    ("lending_capability_off", (), ("loans.enabled",)),
    ("request_workflow_off", ("request_workflow",), ()),
    ("everything_off", ("events", "bookings", "request_workflow"), ("loans.enabled",)),
]


_KEYS = {}


@pytest.fixture(autouse=True)
def stable_encryption_keys():
    """One master/search key pair for the WHOLE test.

    `tests.encryption.conftest.enabled_encryption` mints fresh keys on every entry. Contextual creation
    mints the tenant's DEK on its first call (even one that is then refused), wrapped under that master key;
    a later `enabled_encryption()` entry carries a different master key and cannot unwrap it, so the second
    post of a scenario answers 503 `pii_unavailable`. A scenario posts several times, so the keys are fixed.
    """
    _KEYS.update(master=Fernet.generate_key().decode(), search=Fernet.generate_key().decode())
    yield
    _KEYS.clear()


@contextmanager
def _encrypted():
    with override_settings(PII_ENCRYPTION_ENABLED=True, PII_ENCRYPTION_DUAL_READ=True,
                           PII_MASTER_KEY=_KEYS["master"], PII_KEY_BROKER="local",
                           PII_SEARCH_HASH_KEY=_KEYS["search"]):
        from apps.encryption.blind_index import search_key_fingerprint
        from apps.encryption.models import SearchKeyGeneration

        SearchKeyGeneration.objects.get_or_create(generation=1, defaults={
            "key_fingerprint": search_key_fingerprint(), "status": SearchKeyGeneration.Status.ACTIVE,
            "activated_at": timezone.now()})
        yield


@pytest.fixture(autouse=True)
def quiet_evidence(monkeypatch):
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
                        lambda evidence, max_bytes: EvidenceValidationResult(size=123, content_type="image/png"))


def _switch(space, modules=(), features=()):
    space.refresh_from_db()
    space.enabled_modules = sorted(set(space.enabled_modules) - set(modules))
    space.enabled_features = sorted(set(space.enabled_features) - set(features))
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _restore(space, modules, features):
    space.refresh_from_db()
    space.enabled_modules = modules
    space.enabled_features = features
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _post(actor, space, product, **target):
    url = reverse("hardware_requests:contextual-request-staff", args=[space.pk])
    body = {"operation_id": str(uuid4()), "items": [{"product_id": product.pk, "quantity": 1}],
            "requested_for": "matrix", **target}
    with _encrypted():
        return client_for(actor).post(url, body, format="json")


def _world(slug):
    space, actor, product, requests, event, booking = setup_reports(slug)
    product.is_public = True
    product.save(update_fields=["is_public"])
    borrower = account(slug + "-borrower")
    make_member(space, user=borrower)  # a contextual loan needs an active member borrower
    registration = EventRegistration.objects.create(
        event=event, member=borrower, name="Borrower", email=borrower.email, phone="12345678",
        status=EventRegistration.Status.REGISTERED)
    booking.member = borrower
    booking.save(update_fields=["member"])
    return space, actor, product, requests, event, booking, registration


def _expected(modules, features):
    workflow_on = "request_workflow" not in modules and "loans.enabled" not in features
    # With the lending capability off the request_workflow space is not live, so the subject drill-downs
    # refuse (ReportNotFound) and the summary has no rows.
    loans_on = "loans.enabled" not in features
    return {
        "event_create": workflow_on and "events" not in modules,
        "booking_create": workflow_on and "bookings" not in modules,
        "event_drill": "request_workflow" not in modules and "events" not in modules and loans_on,
        "booking_drill": "request_workflow" not in modules and "bookings" not in modules and loans_on,
        "summary_rows": "request_workflow" not in modules and loans_on,
        "dimensions": "events" not in modules and "bookings" not in modules,
    }


def _assert_surfaces(space, actor, product, event, booking, registration, expected):
    summary = build_loan_purpose_summary(space.pk, actor=actor)
    assert (sum(row["count"] for row in summary.records) == 4) is expected["summary_rows"]
    if expected["summary_rows"]:
        assert summary.meta["context_dimensions_available"] is expected["dimensions"]
    for build, kind, subject, key in (
        (build_event_equipment, "event", event, "event_drill"),
        (build_booking_equipment, "booking", booking, "booking_drill"),
    ):
        if expected[key]:
            assert build(space.pk, actor=actor, subject_kind=kind, subject_id=subject.pk).records
        else:
            with pytest.raises(APIException):
                build(space.pk, actor=actor, subject_kind=kind, subject_id=subject.pk)
    event_reply = _post(actor, space, product, event_registration_id=registration.pk)
    booking_reply = _post(actor, space, product, booking_id=booking.pk)
    for reply, key in ((event_reply, "event_create"), (booking_reply, "booking_create")):
        if expected[key]:
            assert reply.status_code == 201, reply.content
        else:
            assert reply.status_code in (403, 404), (key, reply.status_code)


@pytest.mark.parametrize("scenario, modules, features", SCENARIOS, ids=[row[0] for row in SCENARIOS])
def test_contextual_lending_matrix(scenario, modules, features):
    space, actor, product, requests, event, booking, registration = _world(f"matrix-{scenario}")
    event_links = EventLoanContext.objects.filter(makerspace=space).count()
    booking_links = BookingLoanContext.objects.filter(makerspace=space).count()
    _switch(space, modules, features)

    _assert_surfaces(space, actor, product, event, booking, registration, _expected(modules, features))

    # Disabling a context is not deleting or settling a loan: every link and request survives.
    # (>=: a switch that is still on may legitimately have just linked one more loan.)
    assert EventLoanContext.objects.filter(makerspace=space).count() >= event_links
    assert BookingLoanContext.objects.filter(makerspace=space).count() >= booking_links
    assert HardwareRequest.objects.filter(pk__in=[row.pk for row in requests]).count() == 4

    # Settlement is the core ledger: reachable whatever the optional modules do.
    borrower = requests[1].requester
    charge = Payment.objects.create(
        makerspace=space, member=borrower, created_by=borrower, subject_type=Payment.SubjectType.LOAN_RENTAL,
        subject_id=requests[1].pk, amount="12.00", currency="inr", status=Payment.Status.PENDING)
    reply = client_for(actor).post(
        f"/api/v1/admin/makerspace/{space.pk}/payments/{charge.pk}/mark-offline", settlement_payload(), format="json")
    assert reply.status_code == 200, reply.content
    charge.refresh_from_db()
    assert charge.status == Payment.Status.PAID_OFFLINE


RETURN_SCENARIOS = [row for row in SCENARIOS if "request_workflow" not in row[1] and not row[2]]


@pytest.mark.parametrize("scenario, modules, features", RETURN_SCENARIOS, ids=[row[0] for row in RETURN_SCENARIOS])
def test_return_stays_reachable_while_a_context_module_is_off(scenario, modules, features):
    space, actor, product, requests, event, booking, registration = _world(f"matrix-return-{scenario}")
    loan = make_issued_request(space, actor, [(product, 1)])
    EventLoanContext.objects.create(makerspace=space, request=loan, event=event, active=True)
    BookingLoanContext.objects.create(makerspace=space, request=loan, booking=booking, active=True)
    _switch(space, modules, features)
    payload = return_payload(loan, make_return_evidence(space, actor))
    result = workflow.return_items(actor, loan, payload["evidence_id"], payload["remark"],
                                   payload["box_code"], payload["resolutions"])
    assert result.status == HardwareRequest.Status.RETURNED
    assert EventLoanContext.objects.filter(request=loan, event=event).exists()


def test_switching_everything_off_and_back_on_restores_every_surface():
    space, actor, product, requests, event, booking, registration = _world("matrix-reenable")
    modules, features = list(space.enabled_modules), list(space.enabled_features)
    _switch(space, ("events", "bookings", "request_workflow"), ("loans.enabled",))
    _assert_surfaces(space, actor, product, event, booking, registration,
                     _expected(("events", "bookings", "request_workflow"), ("loans.enabled",)))
    _restore(space, modules, features)
    _assert_surfaces(space, actor, product, event, booking, registration, _expected((), ()))
    assert build_loan_purpose_summary(space.pk, actor=actor).meta["context_dimensions_available"] is True
