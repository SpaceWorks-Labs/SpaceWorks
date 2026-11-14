"""Loan policies change real admission and checklist output; no invented route refusal."""
from datetime import timedelta

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.hardware_requests.pickup_windows import validate_window
from apps.hardware_requests.workflow_errors import RequestValidationError
from apps.inventory.availability_loan_limits import enforce_borrow_limits, borrower_allowance
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.kit_helpers import kit_setup
from tests.modules.switch_matrix_object_helpers import client_for, retained, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, no_domain_writes, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("key", ["loans.limits", "request_workflow"])
def test_limits_policy_off_allows_admission_on_restores_the_saved_cap_without_writes(key):
    space, member, _, product, loan, policy, _ = setup_loan("p1-limits")
    policy.loan_max_active = 1
    policy.save(update_fields=["loan_max_active"])
    objects = {"loan": loan, "product": product, "policy": policy}
    before = retained(objects)
    original = switch(space, key)
    with connection.execute_wrapper(_no_write):
        assert enforce_borrow_limits(space, member, 1) is None
        assert borrower_allowance(space, member) is None
    switch(space, key, original=original)
    with connection.execute_wrapper(_no_write), pytest.raises(ValidationError) as error:
        enforce_borrow_limits(space, member, 1)
    assert error.value.status_code == 400
    assert error.value.detail["code"] == "loan_limit"
    assert borrower_allowance(space, member)["active_loans"] == {"used": 1, "limit": 1}
    assert retained(objects) == before


@pytest.mark.parametrize("key", ["loans.reservations", "request_workflow"])
def test_reservation_policy_retains_window_and_refuses_selection_while_off(key):
    space, _, _, product, loan, _, _ = setup_loan("p1-reservation")
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.reservations"})
    space.save(update_fields=["enabled_features"])
    now = timezone.now()
    start, end = now + timedelta(hours=2), now + timedelta(hours=3)
    loan.pickup_from, loan.pickup_until = start, end
    loan.save(update_fields=["pickup_from", "pickup_until"])
    before = retained({"loan": loan, "product": product})
    assert validate_window(space, start, end, now=now) == (start, end)
    original = switch(space, key)
    with connection.execute_wrapper(_no_write), pytest.raises(RequestValidationError) as error:
        validate_window(space, start, end, now=now)
    assert str(error.value) == "Choosing a pickup time is not available here."
    switch(space, key, original=original)
    assert validate_window(space, start, end, now=now) == (start, end)
    assert retained({"loan": loan, "product": product}) == before


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["loans.kit_checklist", "containers"])
def test_kit_checklist_policy_hides_and_restores_the_same_required_components(native, key):
    data = kit_setup(slug="p1-kit")
    client = client_for(data.actor, data.space, native)
    url = reverse("hardware_requests:staff-kit-preview", kwargs={"makerspace_id": data.space.pk})
    body = {"request_id": data.request.pk}
    before = retained({"loan": data.request, "product": data.product, "box": data.box})
    with no_domain_writes():
        on = client.post(url, body, format="json")
    assert response_pair(on) == (200, None)
    assert on.data["components"]
    original = switch(data.space, key)
    with no_domain_writes():
        off = client.post(url, body, format="json")
    assert response_pair(off) == (200, None)
    assert off.data["components"] == []
    switch(data.space, key, original=original)
    restored = client.post(url, body, format="json")
    assert response_pair(restored) == (200, None)
    assert restored.data == on.data
    assert retained({"loan": data.request, "product": data.product, "box": data.box}) == before
