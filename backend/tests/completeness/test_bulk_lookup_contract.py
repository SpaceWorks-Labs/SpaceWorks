"""Decision 248: row lookups preserve bulk atomicity without disclosing existence."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.admin_api.bulk_decisions import BulkFailed, _BulkView
from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace, Booking
from apps.events.models import EventRegistration
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.inventory.models import InventoryProduct
from apps.integrations.models_contract import NotificationEnvelope
from apps.notifications.models import Notification
from apps.payments.models import Payment, Refund, RefundCase
from tests.events.ticketing_helpers import open_event
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_product, make_space

pytestmark = pytest.mark.django_db

CALLERS = [
    pytest.param("requests", "accept", "accepted", marks=pytest.mark.area_lending),
    pytest.param("bookings", "reject", "rejected", marks=pytest.mark.area_bookings),
    pytest.param("event-registrations", "reject", "rejected", marks=pytest.mark.area_events),
    pytest.param("refund-cases", "decline", "declined", marks=pytest.mark.area_payments_ledger),
]


def _space(slug):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"staff_admin", "request_workflow", "bookings", "events"})
    space.enabled_features = sorted(set(space.enabled_features) | {"events.account_registration"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def _row(kind, space, borrower, actor):
    if kind == "requests":
        row = HardwareRequest.objects.create(makerspace=space, requester=borrower,
            requester_username=borrower.username, status="pending_approval")
        HardwareRequestItem.objects.create(request=row, product=make_product(space), requested_quantity=1)
        return row
    if kind == "bookings":
        start = timezone.now() + timedelta(days=1)
        return Booking.objects.create(space=BookableSpace.objects.create(makerspace=space, name="Room"),
            member=borrower, name=borrower.username, email=borrower.email, starts_at=start,
            ends_at=start + timedelta(hours=1), status="pending")
    if kind == "event-registrations":
        event = open_event(space, registration_requires_approval=True)
        return EventRegistration.objects.create(event=event, member=borrower, name=borrower.username,
            email=borrower.email, phone="12345678", status="pending_approval")
    # A real same-tenant loan subject, never a fabricated payment subject id.
    loan = HardwareRequest.objects.create(makerspace=space, requester=borrower,
        requester_username=borrower.username, status="accepted")
    payment = Payment.objects.create(makerspace=space, member=borrower, created_by=actor,
        subject_type="loan_deposit", subject_id=loan.pk, subject_label="Deposit", amount="10.00",
        currency="usd", provider="stripe", status="paid_online")
    return RefundCase.objects.create(payment=payment, kind="request", area="loans",
        reason_code="member_request", due_amount="10.00", requested_by=borrower)


def _url(kind, decision, space):
    names = {"requests": "admin-bulk-requests", "bookings": "admin-bulk-bookings",
             "event-registrations": "admin-bulk-event-registrations", "refund-cases": "admin-bulk-refund-cases"}
    args = [space.pk, decision] if kind == "refund-cases" else [decision]
    return reverse(names[kind], args=args)


def _single_url(kind, pk, space):
    names = {"requests": "hardware_requests:request-accept", "bookings": "admin-booking-reject",
             "event-registrations": "admin-event-registration-reject", "refund-cases": "refund-case-decline"}
    args = [space.pk, pk] if kind == "refund-cases" else [pk]
    return reverse(names[kind], args=args)


def _snapshot(own):
    models = (type(own), HardwareRequest, HardwareRequestItem, InventoryProduct, Payment, Refund, RefundCase,
              AuditLog, NotificationEnvelope, Notification)
    return {model._meta.label: list(model._base_manager.order_by("pk").values()) for model in models}


@pytest.mark.parametrize("kind,decision,final_status", CALLERS)
def test_missing_and_foreign_bulk_rows_have_identical_contract_and_roll_back(kind, decision, final_status):
    own_space, foreign_space = _space("bulk-own"), _space("bulk-foreign")
    actor = staff_account(own_space, "bulk-manager", "space_manager")
    foreign_actor = staff_account(foreign_space, "bulk-foreign-manager", "space_manager")
    borrower = User.objects.create_user("bulk-borrower", email="borrower@example.test", access_status="active")
    own = _row(kind, own_space, borrower, actor)
    foreign = _row(kind, foreign_space, borrower, foreign_actor)
    missing = max(own.pk, foreign.pk) + 1000000
    client = authenticated_client(actor)
    url = _url(kind, decision, own_space)
    before = _snapshot(own)
    foreign_status = foreign.status
    responses = []
    for bad_id in (missing, foreign.pk):
        response = client.post(url, {"ids": [own.pk, bad_id], "reason": "Reviewed"}, format="json")
        assert response.status_code == 409
        assert response.json() == {"code": "bulk_failed",
            "detail": "Nothing was changed: one item could not be decided.",
            "failed_id": bad_id, "cause": "not_found"}
        assert _snapshot(own) == before
        responses.append({key: value for key, value in response.json().items() if key != "failed_id"})
        single_body = {"note" if kind == "refund-cases" else "reason": "Reviewed"}
        single = client.post(_single_url(kind, bad_id, own_space), single_body, format="json")
        assert single.status_code == 404
        assert single.json()["code"] == "not_found"
        assert _snapshot(own) == before
    assert responses[0] == responses[1]
    # Prove the first row was actually decidable, through the same real service.
    response = client.post(url, {"ids": [own.pk], "reason": "Reviewed"}, format="json")
    assert response.status_code == 200
    assert response.json() == {"decided": 1, "ids": [own.pk]}
    own.refresh_from_db()
    foreign.refresh_from_db()
    assert own.status == final_status
    assert foreign.status == foreign_status
    action = {"requests": "request.accepted", "bookings": "booking.rejected",
              "event-registrations": "event.registration_rejected", "refund-cases": "payment.refund_case_declined"}[kind]
    assert AuditLog.objects.filter(makerspace=own_space, actor=actor, action=action).count() == 1


@pytest.mark.parametrize("failure", [Http404("private model text"),
    HardwareRequest.DoesNotExist("private lookup text"), NotFound("private refund text")])
def test_runner_normalizes_each_lookup_exception_and_rolls_back_earlier_writes(failure):
    actor = User.objects.create_user("bulk-runner", display_name="Before")

    class LookupView(_BulkView):
        def decide(self, actor, pk, decision, reason):
            if pk == 2:
                raise failure
            User.objects.filter(pk=actor.pk).update(display_name="Changed")

    request = SimpleNamespace(user=actor, data={"ids": [1, 2]})
    with pytest.raises(BulkFailed) as caught:
        LookupView().post(request, "reject")
    assert caught.value.status_code == 409
    assert caught.value.detail == {"code": "bulk_failed",
        "detail": "Nothing was changed: one item could not be decided.", "failed_id": 2, "cause": "not_found"}
    actor.refresh_from_db()
    assert actor.display_name == "Before"


@pytest.mark.parametrize("gate_kind,key", [("module", "events"), ("feature", "events.checkin_lists")])
def test_structured_disabled_gate_causes_keep_their_existing_typed_contract(gate_kind, key):
    from apps.makerspaces.guards import SurfaceOff

    class DisabledView(_BulkView):
        def decide(self, actor, pk, decision, reason):
            raise SurfaceOff(gate_kind, key)

    with pytest.raises(BulkFailed) as caught:
        DisabledView().post(SimpleNamespace(user=None, data={"ids": [7]}), "reject")
    assert caught.value.status_code == 409
    assert caught.value.detail == {"code": "bulk_failed",
        "detail": "Nothing was changed: one item could not be decided.", "failed_id": 7,
        "cause": {"detail": f"{key} is turned off for this makerspace.",
                  "code": f"{gate_kind}_disabled", gate_kind: key}}


@pytest.mark.parametrize("kind,decision,final_status", CALLERS[:-1])
def test_real_bulk_module_disable_restore_retains_rows_and_restores_decisions(kind, decision, final_status):
    space = _space("bulk-module-cycle")
    actor = staff_account(space, "bulk-cycle-manager", "space_manager")
    borrower = User.objects.create_user("bulk-cycle-borrower", email="cycle@example.test", access_status="active")
    row = _row(kind, space, borrower, actor)
    client = authenticated_client(actor)
    url = _url(kind, decision, space)
    module = {"requests": "request_workflow", "bookings": "bookings", "event-registrations": "events"}[kind]
    enabled = list(space.enabled_modules)
    before = _snapshot(row)
    space.enabled_modules = [key for key in enabled if key != module]
    space.save(update_fields=["enabled_modules"])
    refused = client.post(url, {"ids": [row.pk], "reason": "Reviewed"}, format="json")
    assert refused.status_code == 409
    assert refused.json() == {"code": "bulk_failed",
        "detail": "Nothing was changed: one item could not be decided.", "failed_id": row.pk,
        "cause": {"detail": f"{module} is turned off for this makerspace.",
                  "code": "module_disabled", "module": module}}
    assert _snapshot(row) == before
    space.enabled_modules = enabled
    space.save(update_fields=["enabled_modules"])
    assert _snapshot(row) == before
    restored = client.post(url, {"ids": [row.pk], "reason": "Reviewed"}, format="json")
    assert restored.status_code == 200
    assert restored.json() == {"decided": 1, "ids": [row.pk]}
    row.refresh_from_db()
    assert row.status == final_status
    action = {"requests": "request.accepted", "bookings": "booking.rejected",
              "event-registrations": "event.registration_rejected"}[kind]
    assert AuditLog.objects.filter(makerspace=space, actor=actor, action=action).count() == 1


@pytest.mark.area_payments_ledger
def test_real_refund_bulk_decline_survives_removed_payment_rail(settings):
    space = _space("bulk-decline-no-rail")
    actor = staff_account(space, "bulk-decline-manager", "space_manager")
    borrower = User.objects.create_user("bulk-decline-borrower", email="decline@example.test", access_status="active")
    cases = [_row("refund-cases", space, borrower, actor) for _ in range(2)]
    payments_before = list(Payment.objects.order_by("pk").values())
    settings.TOMBSTONED_APPS = frozenset(settings.TOMBSTONED_APPS) | {"payments_rail"}
    response = authenticated_client(actor).post(_url("refund-cases", "decline", space),
        {"ids": [case.pk for case in cases], "reason": "Reviewed"}, format="json")
    assert response.status_code == 200
    assert response.json() == {"decided": 2, "ids": [case.pk for case in cases]}
    for case in cases:
        case.refresh_from_db()
        assert (case.status, case.decision_note, case.decided_by_id, case.refund_id) == (
            "declined", "Reviewed", actor.pk, None)
    assert list(Payment.objects.order_by("pk").values()) == payments_before
    assert Refund.objects.count() == 0
    assert AuditLog.objects.filter(makerspace=space, actor=actor, action="payment.refund_case_declined").count() == 2


@pytest.mark.area_payments_ledger
@pytest.mark.parametrize("remove_after_first", [False, True])
def test_real_refund_bulk_approval_rail_refusal_rolls_back_and_discards_dispatch(
        settings, monkeypatch, django_capture_on_commit_callbacks, remove_after_first):
    from apps.payments import services_refund_decisions as decisions

    space = _space("bulk-approve-rail")
    actor = staff_account(space, "bulk-approve-manager", "space_manager")
    borrower = User.objects.create_user("bulk-approve-borrower", email="approve@example.test", access_status="active")
    cases = [_row("refund-cases", space, borrower, actor) for _ in range(2)]
    before, completed, dispatched = _snapshot(cases[0]), [], []
    removed = frozenset(settings.TOMBSTONED_APPS) | {"payments_rail"}
    monkeypatch.setattr("apps.payments.services_refunds.dispatch_refund",
                        lambda refund, **kwargs: dispatched.append(refund.pk))
    if remove_after_first:
        approve = decisions.approve_case

        def approve_then_remove_rail(case, **kwargs):
            # Execute the real service, then change only deployment configuration.
            result = approve(case, **kwargs)
            assert (result.status, result.refund.status) == ("approved", "pending")
            assert Refund.objects.filter(pk=result.refund_id, payment_id=case.payment_id).count() == 1
            assert AuditLog.objects.filter(action="payment.refund_case_approved", meta__case_id=case.pk).count() == 1
            completed.append(case.pk)
            settings.TOMBSTONED_APPS = removed
            return result

        monkeypatch.setattr(decisions, "approve_case", approve_then_remove_rail)
    else:
        settings.TOMBSTONED_APPS = removed
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = authenticated_client(actor).post(_url("refund-cases", "approve", space),
            {"ids": [case.pk for case in cases]}, format="json")
    assert response.status_code == 409
    assert response.json() == {"code": "bulk_failed",
        "detail": "Nothing was changed: one item could not be decided.",
        "failed_id": cases[1 if remove_after_first else 0].pk,
        "cause": {"code": "refund_rail_unavailable",
                  "detail": "Online refunds are not available on this deployment; decline instead."}}
    assert completed == ([cases[0].pk] if remove_after_first else [])
    assert _snapshot(cases[0]) == before
    assert callbacks == []
    assert dispatched == []


@pytest.fixture(scope="module")
def bulk_schema_document():
    from drf_spectacular.drainage import GENERATOR_STATS
    from drf_spectacular.generators import SchemaGenerator

    GENERATOR_STATS.reset()
    return SchemaGenerator().get_schema(request=None, public=True)


@pytest.mark.area_lending
@pytest.mark.area_bookings
@pytest.mark.area_events
@pytest.mark.area_payments_ledger
@pytest.mark.area_staff_admin
@pytest.mark.area_api_contract
def test_real_bulk_409_schema_has_distinct_component_and_exact_required_fields(bulk_schema_document):
    from apps.openapi_contract.check import component_collisions

    document = bulk_schema_document
    paths = [f"/api/v1/admin/bulk/{kind}/{{decision}}" for kind in ("requests", "bookings", "event-registrations")]
    paths += ["/api/v1/admin/makerspaces/{makerspace_id}/refund-cases/bulk/{decision}",
              "/api/v1/admin/makerspaces/{makerspace_id}/staff-roles/bulk-invite/"]
    for path in paths:
        responses = document["paths"][path]["post"]["responses"]
        assert responses["409"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/BulkFailure"}
        assert responses["404"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/HardwareRequestError"}
    schemas = document["components"]["schemas"]
    assert set(schemas["BulkFailure"]["properties"]) == {"detail", "code", "failed_id", "cause"}
    assert set(schemas["BulkFailure"]["required"]) == {"detail", "code", "failed_id", "cause"}
    assert set(schemas["HardwareRequestError"]["properties"]) == {"detail", "code"}
    assert set(schemas["HardwareRequestError"]["required"]) == {"detail", "code"}
    assert component_collisions() == []
