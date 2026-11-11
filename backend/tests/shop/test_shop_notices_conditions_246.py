"""Decision 246 (lane T4): service-level conditions for shop notices (221f) and shop webhooks (221h).

Calls `notices.staff_notice`, `notices.buyer_notice`, `notices.eligible` and
`webhooks.order_webhook` directly. Asserts recipients by role and preference, replay without a
duplicate envelope, silence with the shop module off, no recipient from another space, ids-only
webhook payloads, the webhook gate, and that a failed webhook insert does not poison the caller's
transaction.
"""
import pytest
from django.utils import timezone
from django.db import DatabaseError, transaction

from apps.integrations.models import NotificationDeliveryLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.makerspaces.models import MakerspaceMembership
from apps.shop import notices, webhooks
from apps.shop.models import ShopOrder

from .helpers import manager, module_off, product, shop_manager, shop_space, staff
from .test_hold_return_refund_coordination import _paid_online

pytestmark = pytest.mark.django_db(transaction=True)


def paid_order(slug):
    space = shop_space(slug, "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    return space, seller, _paid_online(space, variant, qty=1, buyer=f"{slug}-buyer")


def staff_envelopes(order, event="shop_order_new"):
    return NotificationEnvelope.objects.filter(event=event, source_id=str(order.pk), audience="staff")


def test_staff_notice_reaches_shop_authority_only_and_never_another_space():
    space, seller, order = paid_order("t246-shop-a")
    plain = staff(space, "member", "t246-shop-a-plain")
    other_space = shop_space("t246-shop-b", "shop.online")
    other_manager = shop_manager(other_space)
    notices.staff_notice(space, order, "shop_order_new")
    heard = set(staff_envelopes(order).values_list("recipient_id", flat=True))
    assert seller.pk in heard
    assert plain.pk not in heard and other_manager.pk not in heard
    assert set(staff_envelopes(order).values_list("makerspace_id", flat=True)) == {space.pk}


def test_staff_who_opted_out_of_notifications_hear_nothing():
    space, seller, order = paid_order("t246-shop-pref")
    MakerspaceMembership.all_tracks.filter(makerspace=space, user=seller).update(receives_notifications=False)
    boss = manager(space)
    # paying the order already announced `shop_order_new` to the seller, so a fresh event shows the opt-out
    notices.staff_notice(space, order, "shop_order_unfulfilled")
    heard = set(staff_envelopes(order, "shop_order_unfulfilled").values_list("recipient_id", flat=True))
    assert seller.pk not in heard
    assert boss.pk in heard


def test_replaying_a_staff_or_buyer_notice_creates_no_second_envelope():
    space, _seller, order = paid_order("t246-shop-replay")
    notices.staff_notice(space, order, "shop_order_new")
    notices.buyer_notice(order, "shop_order_ready")
    first = NotificationEnvelope.objects.filter(source_id=str(order.pk)).count()
    assert first > 0
    notices.staff_notice(space, order, "shop_order_new")
    notices.buyer_notice(order, "shop_order_ready")
    assert NotificationEnvelope.objects.filter(source_id=str(order.pk)).count() == first


def test_unknown_notice_events_are_swallowed_without_an_envelope():
    space, _seller, order = paid_order("t246-shop-unknown")
    before = NotificationEnvelope.objects.count()
    assert not getattr(notices.staff_notice(space, order, "shop_order_bogus"), "scheduled", False)  # safe_notification result
    assert not getattr(notices.buyer_notice(order, "shop_order_bogus"), "scheduled", False)
    assert NotificationEnvelope.objects.count() == before


def test_a_guest_order_without_an_email_sends_nothing():
    space, _seller, order = paid_order("t246-shop-guest")
    ShopOrder.objects.filter(pk=order.pk).update(buyer=None, guest_email="")
    order.refresh_from_db()
    before = NotificationEnvelope.objects.count()
    assert notices.buyer_notice(order, "shop_order_ready") is None
    assert NotificationEnvelope.objects.count() == before


def test_a_queued_notice_is_stale_once_the_shop_module_is_off_or_the_role_is_lost():
    space, seller, order = paid_order("t246-shop-off")
    notices.staff_notice(space, order, "shop_order_new")
    notices.buyer_notice(order, "shop_order_ready")
    staff_row = staff_envelopes(order).filter(recipient=seller).order_by("-pk").first()
    buyer_row = NotificationEnvelope.objects.get(event="shop_order_ready", source_id=str(order.pk))
    assert notices.eligible(staff_row) and notices.eligible(buyer_row)
    MakerspaceMembership.objects.filter(makerspace=space, user=seller).update(status="suspended")
    assert not notices.eligible(staff_row)
    module_off(space)
    assert not notices.eligible(buyer_row)


def test_webhook_payload_is_ids_and_time_only_and_names_no_buyer_or_amount(monkeypatch):
    space, _seller, order = paid_order("t246-hook-pii")
    order = ShopOrder.objects.select_related("makerspace", "buyer").get(pk=order.pk)
    from apps.integrations import notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: True)
    for event in webhooks.EVENTS:
        assert webhooks.order_webhook(order, event) is True
        row = NotificationDeliveryLog.objects.filter(makerspace=space, event=event).latest("pk")
        assert set(row.payload) == {"shop_order_id", "occurred_at"}
        assert row.payload["shop_order_id"] == order.pk
        blob = f"{row.text_body} {row.payload}"
        assert order.pickup_code not in blob and order.buyer.username not in blob
        assert str(order.amount_due) not in row.payload.values().__str__()


def test_webhook_is_gated_by_module_cell_and_event_name(monkeypatch):
    space, _seller, order = paid_order("t246-hook-gate")
    order = ShopOrder.objects.select_related("makerspace", "buyer").get(pk=order.pk)
    from apps.integrations import notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: True)
    with pytest.raises(ValueError):
        webhooks.order_webhook(order, "shop_order_bogus")
    module_off(space)
    order = ShopOrder.objects.select_related("makerspace", "buyer").get(pk=order.pk)
    assert webhooks.order_webhook(order, "shop_order_picked_up") is False
    assert not NotificationDeliveryLog.objects.filter(makerspace=space, event="shop_order_picked_up").exists()


def test_a_failed_webhook_insert_returns_false_and_leaves_the_callers_transaction_usable(monkeypatch):
    space, _seller, order = paid_order("t246-hook-savepoint")
    order = ShopOrder.objects.select_related("makerspace", "buyer").get(pk=order.pk)
    from apps.integrations import dispatch_channels, notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: True)

    def explode(**kwargs):
        raise DatabaseError("insert failed")

    monkeypatch.setattr(dispatch_channels, "dispatch_channel", explode)
    with transaction.atomic():
        assert webhooks.order_webhook(order, "shop_order_ready_for_pickup") is False
        ShopOrder.objects.filter(pk=order.pk).update(status="collected", collected_at=timezone.now())  # the order flow carries on
    assert ShopOrder.objects.get(pk=order.pk).status == "collected"


def test_handover_event_follows_where_the_order_was_collected():
    class Order:
        pickup_at = "event"
    assert webhooks.handover_event(Order()) == "shop_order_delivered"
    Order.pickup_at = "space"
    assert webhooks.handover_event(Order()) == "shop_order_picked_up"
