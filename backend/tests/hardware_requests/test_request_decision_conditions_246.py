"""Decision 246: accept / reject of a borrow request across every built-in role, replay, stock and isolation.

Authority is `accept_request` (read from `ROLE_CATALOG`). Inventory quantity math must move exactly once
(reserve on accept, nothing on reject) and a decided request cannot be decided again.
"""
import pytest

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_product, make_space
from tests.test_request_workflow import accept_url, make_hardware_request, reject_url

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]


def _world(slug, quantity=2, stock=5):
    space = make_space(slug)
    product = make_product(space, total_quantity=stock, available_quantity=stock)
    return space, product, make_hardware_request(space, product, quantity=quantity)


@pytest.mark.parametrize("decision", ["accept", "reject"])
@pytest.mark.parametrize("slug", SLUGS)
def test_decision_follows_accept_request_for_every_built_in_role(slug, decision):
    space, product, request = _world(f"rd-{slug}-{decision}".replace("_", "-"))
    actor = staff_account(space, f"rd-actor-{slug}-{decision}", slug)
    url = accept_url(request) if decision == "accept" else reject_url(request)
    body = {} if decision == "accept" else {"reason": "No stock for that week"}
    response = authenticated_client(actor).post(url, body, format="json")
    request.refresh_from_db()
    product.refresh_from_db()
    if "accept_request" in ROLE_BY_SLUG[slug].granted_actions:
        assert response.status_code == 200, response.content
        assert request.status == (HardwareRequest.Status.ACCEPTED if decision == "accept"
                                  else HardwareRequest.Status.REJECTED)
        assert product.reserved_quantity == (2 if decision == "accept" else 0)
        assert AuditLog.objects.filter(makerspace=space, actor=actor, target_id=str(request.pk)).exists()
    else:
        assert response.status_code in (403, 404)
        assert request.status == HardwareRequest.Status.PENDING_APPROVAL
        assert product.reserved_quantity == 0 and product.available_quantity == 5
        assert not AuditLog.objects.filter(makerspace=space, actor=actor).exists()


def test_a_decided_request_cannot_be_decided_again_and_stock_moves_once():
    space, product, request = _world("rd-replay")
    boss = authenticated_client(staff_account(space, "rd-replay-boss", "space_manager"))
    assert boss.post(accept_url(request), {}, format="json").status_code == 200
    again = boss.post(accept_url(request), {}, format="json")
    flipped = boss.post(reject_url(request), {"reason": "changed my mind"}, format="json")
    assert again.status_code in (400, 409) and flipped.status_code in (400, 409)
    product.refresh_from_db()
    assert (product.reserved_quantity, product.available_quantity) == (2, 3)
    assert AuditLog.objects.filter(action="request.accepted", target_id=str(request.pk)).count() == 1


def test_accepting_more_than_the_stock_is_refused_without_changing_quantities():
    space, product, request = _world("rd-stock", quantity=9, stock=5)
    boss = authenticated_client(staff_account(space, "rd-stock-boss", "space_manager"))
    response = boss.post(accept_url(request), {}, format="json")
    assert response.status_code == 409
    product.refresh_from_db()
    request.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity) == (5, 0)
    assert request.status == HardwareRequest.Status.PENDING_APPROVAL


def test_another_spaces_manager_cannot_decide_and_anonymous_is_refused():
    from rest_framework.test import APIClient
    space, product, request = _world("rd-iso-a")
    other = make_space("rd-iso-b")
    outsider = authenticated_client(staff_account(other, "rd-iso-outsider", "space_manager"))
    assert outsider.post(accept_url(request), {}, format="json").status_code in (403, 404)
    assert outsider.post(reject_url(request), {"reason": "x"}, format="json").status_code in (403, 404)
    assert APIClient().post(accept_url(request), {}, format="json").status_code in (401, 403)
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.PENDING_APPROVAL


def test_an_unknown_request_id_is_404():
    space, _product, _request = _world("rd-missing")
    boss = authenticated_client(staff_account(space, "rd-missing-boss", "space_manager"))
    assert boss.post("/api/v1/admin/requests/987654/accept", {}, format="json").status_code == 404
