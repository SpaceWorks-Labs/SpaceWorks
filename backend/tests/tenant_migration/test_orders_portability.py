"""L6 portability: orders, holds and dues are in the money fingerprint; tokens are re-minted on a move."""

import pytest

from apps.data_export.fields import ALWAYS_OMITTED
from apps.events.models import EventOrder
from apps.tenant_migration.money_digest import money_fingerprint
from apps.tenant_migration.money_digest_r2_l6 import l6_money_rows
from apps.tenant_migration.omitted_fields import FRESH, OMITTED_FIELD_RECONSTRUCTIONS
from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS
from apps.tenant_migration.unique_values import DEPLOYMENT_GLOBAL_UNIQUE_RULES
from tests.events.orders_helpers import order_payment, place, settle_offline, ticketed_event, verified

pytestmark = pytest.mark.django_db


def test_orders_and_holds_move_the_money_fingerprint(django_capture_on_commit_callbacks):
    space, event, staff, ticket = ticketed_event(amount=9)
    assert l6_money_rows(space.pk) == {}
    before = money_fingerprint(space.pk)
    place(verified("buyer"), event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    placed = money_fingerprint(space.pk)
    assert placed != before and set(l6_money_rows(space.pk)) >= {"event_orders", "event_checkout_holds"}
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(order_payment(EventOrder.objects.get()), staff)
    assert money_fingerprint(space.pk) != placed


def test_claim_and_transfer_tokens_never_travel():
    for label, field in (("events.EventOrderSeat", "claim_token_digest"), ("events.EventTicketTransfer", "token_digest")):
        assert (label, field) in ALWAYS_OMITTED
        assert OMITTED_FIELD_RECONSTRUCTIONS[(label, field)] is FRESH
        assert (label, f"field:{field}") in DEPLOYMENT_GLOBAL_UNIQUE_RULES
    assert {"events.EventOrder", "events.EventOrderSeat", "events.EventOrderDue", "events.EventVenueFee"} <= set(
        PROJECTED_MODEL_LABELS)
