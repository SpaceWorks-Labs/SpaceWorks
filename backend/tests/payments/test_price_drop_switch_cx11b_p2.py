"""Price-drop policy opens entitlements, never refunds money, and leaves prior cases intact."""
from decimal import Decimal

import pytest
from django.db import connection, transaction

from apps.payments.models import Refund, RefundCase
from apps.payments.price_drop.find_tickets import find_tickets
from apps.payments.price_drop.hook import on_price_change
from tests.l24_local.helpers import l24_space
from tests.l24_local.test_price_drop_tickets import sold_ticket
from tests.modules.switch_matrix_object_helpers import retained
from tests.payments.switch_helpers_cx11b_p2 import _no_write, domain_rows, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger, pytest.mark.area_events]


def test_price_drop_policy_is_inert_off_then_opens_one_entitlement_for_same_paid_ticket():
    space, actor = l24_space("p2-price-drop", modules=("events",), features=("events.ticket_types",))
    event, ticket, registration, payment = sold_ticket(space, "p2-price-drop")
    ticket.amount = Decimal("15")
    ticket.save(update_fields=["amount"])
    objects = {"event": event, "ticket": ticket, "registration": registration, "payment": payment}
    before, rows = retained(objects), domain_rows()
    original = switch(space, "charges.price_drop_refunds")
    def apply():
        return on_price_change(actor, space, "events", target=ticket,
            find=lambda: find_tickets(event, ticket_type=ticket))
    with connection.execute_wrapper(_no_write):
        assert apply() == []
    assert retained(objects) == before and domain_rows() == rows
    switch(space, "charges.price_drop_refunds", original=original)
    with transaction.atomic():
        cases = apply()
    assert len(cases) == 1
    case = RefundCase.objects.get(pk=cases[0].pk)
    assert (case.payment_id, case.reason_code, case.due_amount) == (payment.pk, "price_drop", Decimal("5"))
    assert Refund.objects.count() == 0
    assert retained(objects) == before
    before = retained({"case": case, **objects})
    original = switch(space, "charges.price_drop_refunds")
    with connection.execute_wrapper(_no_write):
        assert apply() == []
    switch(space, "charges.price_drop_refunds", original=original)
    with transaction.atomic():
        assert apply() == []
    assert retained({"case": case, **objects}) == before
    assert RefundCase.objects.filter(payment=payment).count() == 1
    from apps.audit.models import AuditLog
    assert AuditLog.objects.filter(makerspace=space, action="pricing.price_drop_refunds_opened").count() == 1
