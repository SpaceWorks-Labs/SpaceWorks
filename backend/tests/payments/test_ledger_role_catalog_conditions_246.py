"""Decision 246: the payment ledger across every built-in role, plus replay, validation and isolation.

`test_rbac_f6_finance.py` proves the custom-grant matrix; this file derives the same expectation from
`ROLE_CATALOG` so a role added or re-granted later is checked without hand-editing, and adds the
money-session rules the f6 file leaves open (double settle, bad receipt, foreign payment id).
"""
import pytest

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from apps.payments.models import ManualSettlement
from tests.fixed_roles.helpers import staff_account
from tests.payments.test_rbac_f6_finance import finance_route
from tests.return_helpers import authenticated_client, make_space, settlement_payload
from tests.rbac_f6_helpers import charge, community_member

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]
READ_CASES = ["list", "report"]
WRITE_CASES = ["mark", "bulk", "amend", "refund"]


@pytest.mark.parametrize("case", READ_CASES + WRITE_CASES)
@pytest.mark.parametrize("slug", SLUGS)
def test_every_built_in_role_gets_exactly_the_finance_action_it_holds(slug, case):
    space = make_space(f"led-{slug}-{case}".replace("_", "-"))
    payment, (method, path, body) = finance_route(case, space)
    action = rbac.Action.VIEW_FINANCE if case in READ_CASES else rbac.Action.RECORD_PAYMENT
    actor = staff_account(space, f"led-actor-{slug}-{case}", slug)
    response = getattr(authenticated_client(actor), method)(path, body, format="json")
    if action in ROLE_BY_SLUG[slug].granted_actions:
        assert response.status_code == 200, response.content
    else:
        assert response.status_code in (403, 404)
        assert not AuditLog.objects.filter(actor=actor, makerspace=space).exists()
        payment.refresh_from_db()
        assert payment.status in {"pending", "paid_offline"}


def test_settling_the_same_charge_twice_is_refused_and_records_one_receipt():
    space = make_space("led-twice")
    payment, (_m, path, body) = finance_route("mark", space)
    boss = authenticated_client(staff_account(space, "led-twice-boss", "space_manager"))
    first = boss.post(path, body, format="json")
    second = boss.post(path, body, format="json")
    assert first.status_code == 200
    assert second.status_code in (400, 409)
    assert ManualSettlement.objects.filter(payment=payment).count() == 1


@pytest.mark.parametrize("override", [{"method": ""}, {"method": "barter"}, {"received_at": "yesterday-ish"}])
def test_an_incomplete_or_malformed_receipt_never_settles_the_charge(override):
    space = make_space("led-receipt")
    payment, (_m, path, _body) = finance_route("mark", space)
    boss = authenticated_client(staff_account(space, "led-receipt-boss", "space_manager"))
    response = boss.post(path, settlement_payload(**override), format="json")
    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == "pending" and not ManualSettlement.objects.exists()


def test_a_managers_payment_id_from_another_space_is_not_found_and_untouched():
    mine, theirs = make_space("led-iso-a"), make_space("led-iso-b")
    foreign = charge(theirs, community_member(theirs), status="pending")
    boss = authenticated_client(staff_account(mine, "led-iso-boss", "space_manager"))
    for verb, tail in (("post", "mark-offline"), ("post", "waive")):
        response = getattr(boss, verb)(f"/api/v1/admin/makerspace/{mine.pk}/payments/{foreign.pk}/{tail}",
                                       settlement_payload(), format="json")
        assert response.status_code == 404
    listed = boss.get(f"/api/v1/admin/makerspace/{mine.pk}/payments")
    assert listed.status_code == 200 and all(row["id"] != foreign.pk for row in listed.json()["results"])
    foreign.refresh_from_db()
    assert foreign.status == "pending"


def test_the_list_validates_its_filters():
    space = make_space("led-filter")
    boss = authenticated_client(staff_account(space, "led-filter-boss", "space_manager"))
    base = f"/api/v1/admin/makerspace/{space.pk}/payments"
    assert boss.get(base, {"status": "not-a-status"}).status_code == 400
    assert boss.get(base, {"subject_type": "not-a-subject"}).status_code == 400
