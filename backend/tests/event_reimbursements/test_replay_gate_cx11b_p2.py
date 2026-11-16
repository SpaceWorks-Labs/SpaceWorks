"""Decision 520: disabled crew/staff claims refuse even a previously committed operation."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.event_reimbursements import pools, staff_claims
from apps.event_reimbursements.models import GrantRequest
from apps.events.models import EventCommandReceipt, EventRegistration
from apps.makerspaces.guards import SurfaceOff
from tests.event_reimbursements.conftest import cmd
from tests.modules.switch_matrix_object_helpers import client_for, response_pair, retained
from tests.payments.switch_helpers_cx11b_p2 import _no_write, domain_rows, no_domain_writes, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_events,
              pytest.mark.area_event_reimbursements, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("kind", ["crew", "staff"])
@pytest.mark.parametrize("gate", ["feature", "events", "event_reimbursements"])
def test_committed_command_replay_refuses_off_without_writes_then_returns_original_once(world, kind, gate):
    key = f"events.{kind}_claims"
    world.space.enabled_features = sorted(set(world.space.enabled_features) | {key, "events.crew"})
    world.space.save(update_fields=["enabled_features"])
    if kind == "crew":
        command, data = pools.create_crew_pool, cmd(initial_total_minor=50000)
    else:
        registration = EventRegistration.objects.create(event=world.event, member=world.manager,
            name="Retained staff claimant", email="staff@example.test", status="registered")
        command, data = staff_claims.file_claim, cmd(amount_minor=10000, currency="INR", category="rail",
                                                    beneficiary_registration_id=registration.pk, note="Travel")
    kwargs = {"request": world.finance, "event_id": world.event.pk, "data": data}
    result = command(**kwargs)
    assert command(**kwargs) == result
    receipts = EventCommandReceipt.objects.filter(event=world.event, operation_uuid=data["operation_id"])
    assert receipts.count() == 1
    objects = {"programme": world.programme, "pool": world.pool, "receipt": receipts.get()}
    if kind == "staff":
        objects["claim"] = GrantRequest.objects.get(pk=result["id"])
    before, rows, audits = retained(objects), domain_rows(), AuditLog.objects.count()
    disabled_key = key if gate == "feature" else gate
    original = switch(world.space, disabled_key)
    with connection.execute_wrapper(_no_write), pytest.raises(SurfaceOff) as error:
        command(**kwargs)
    assert error.value.status_code == 404
    assert str(error.value.detail["code"]) == ("feature_disabled" if gate == "feature" else "module_disabled")
    assert error.value.key == disabled_key
    assert retained(objects) == before and domain_rows() == rows
    assert AuditLog.objects.count() == audits
    switch(world.space, disabled_key, original=original)
    with connection.execute_wrapper(_no_write):
        assert command(**kwargs) == result
    assert retained(objects) == before and domain_rows() == rows
    assert receipts.count() == 1 and AuditLog.objects.count() == audits


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind", ["crew", "staff"])
def test_http_replay_checks_capability_before_returning_saved_reference(world, native, kind):
    from tests.accounts.test_reauthentication import PASSWORD
    key = f"events.{kind}_claims"
    world.space.enabled_features = sorted(set(world.space.enabled_features) | {key, "events.crew"})
    world.space.save(update_fields=["enabled_features"])
    client = client_for(world.manager, world.space, native)
    if native:
        from tests.modules.test_switch_matrix_objects_rest_additional_support import reauthenticate
        reauthenticate(client, world.manager, password=PASSWORD)
    if kind == "crew":
        data = cmd(initial_total_minor=50000)
        name = "admin-event-reimbursement-crew-pool"
    else:
        registration = EventRegistration.objects.create(event=world.event, member=world.manager,
            name="Retained staff claimant", email="staff@example.test", status="registered")
        data = cmd(amount_minor=10000, currency="INR", category="rail", beneficiary_registration_id=registration.pk)
        name = "admin-event-reimbursement-staff-claim"
    data["operation_id"] = str(data["operation_id"])
    url = reverse(name, kwargs={"pk": world.event.pk})
    def send():
        return client.post(url, data, format="json", HTTP_IDEMPOTENCY_KEY=data["operation_id"])
    response = send()
    assert response_pair(response) == (201, None), response.data
    reference, rows = response.data, domain_rows()
    original = switch(world.space, key)
    with no_domain_writes():
        refused = send()
    assert response_pair(refused) == (404, "feature_disabled"), refused.data
    assert refused.data["feature"] == key
    assert domain_rows() == rows
    switch(world.space, key, original=original)
    with no_domain_writes():
        replay = send()
    assert response_pair(replay) == (201, None) and replay.data == reference
    assert domain_rows() == rows
    assert EventCommandReceipt.objects.filter(event=world.event, operation_uuid=data["operation_id"]).count() == 1
