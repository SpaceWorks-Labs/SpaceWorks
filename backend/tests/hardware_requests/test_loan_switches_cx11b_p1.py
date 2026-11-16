"""Seeded loan routes: disabled switches refuse before writes on both transports."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanWaitlistEntry
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.return_helpers import make_member, make_product

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["loans.renewals", "request_workflow"])
def test_renewal_switch_keeps_issued_loan_and_restores_due_extension(key, native):
    space, _, _, product, loan, policy, _ = setup_loan("p1-renewal")
    actor = make_member("p1-renewal-manager", space)
    path = reverse("hardware_requests:staff-loan-renew", kwargs={"makerspace_id": space.pk, "pk": loan.pk})
    prove_route(space, client_for(actor, space, native), {"loan": loan, "product": product, "policy": policy},
                key, lambda c: c.post(path, {}, format="json"),
                off=(404, "module_disabled" if key == "request_workflow" else "feature_disabled"))
    loan.refresh_from_db()
    assert loan.renewal_count == 1


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["loans.enabled", "loans.waitlist", "request_workflow", "notifications"])
def test_waitlist_switch_keeps_the_same_owner_entry(key, native):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    product = make_product(space, available_quantity=0, total_quantity=1, issued_quantity=1)
    entry = LoanWaitlistEntry.objects.create(makerspace=space, product=product, user=actor, quantity=1)
    path = reverse("hardware_requests:member-loan-waitlist", kwargs={"makerspace_id": space.pk})
    module_off = key in {"request_workflow", "loans.enabled"}
    prove_route(space, client, {"entry": entry, "product": product}, key, lambda c: c.get(path),
                off=(404, "module_disabled" if module_off else "feature_disabled"),
                refusal_key="request_workflow" if module_off else "loans.waitlist",
                check=lambda r: _contains(r, entry.pk))


def _contains(response, pk):
    assert [row["id"] for row in response.data] == [pk]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["loans.withdrawals", "loans.enabled", "request_workflow"])
def test_withdraw_switch_preserves_pending_request_then_restores_owner_command(key, native):
    space, client, _ = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    loan = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
                                           status="pending_approval")
    path = reverse("hardware_requests:member-request-withdraw", kwargs={"makerspace_id": space.pk, "pk": loan.pk})
    module_off = key in {"request_workflow", "loans.enabled"}
    prove_route(space, client, {"loan": loan}, key, lambda c: c.post(path, {"reason": "Plans changed"}, format="json"),
                off=(404, "module_disabled" if module_off else "feature_disabled"),
                refusal_key="request_workflow" if module_off else "loans.withdrawals")
    loan.refresh_from_db()
    assert loan.status == "cancelled"

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
