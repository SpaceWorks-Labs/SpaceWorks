"""Receipt availability and delivery failures preserve the sale and its ledger."""
from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.integrations.models import NotificationPreference
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.payments.models import ManualSettlement
from apps.shop.models import ShopOrder
from apps.shop.receipts import email_receipt, receipt_payload
from apps.shop.services_pos import pos_sale
from apps.shop.webhooks import order_webhook
from tests.shop.helpers import client, line, manager, payment_for, product, shop_space, switch

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def inline_fanout(settings, monkeypatch):
    settings.NOTIFICATION_FANOUT_VIA_CELERY = False
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda *_: None)


def sale(slug):
    space = shop_space(slug, "shop.receipts")
    actor = manager(space)
    _, variant = product(space, actor, stock=3, price="100")
    order = pos_sale(space, actor=actor, lines=[line(variant)], method="upi", reference="UTR-cx4")
    return space, actor, order


def test_receipt_capability_and_module_restore_the_same_sale_and_settlement():
    space, actor, order = sale("cx4-shop-receipt")
    from django.urls import reverse
    path = reverse("admin-shop-order-receipt", kwargs={"pk": order.pk})
    first = client(actor).get(path)
    assert first.status_code == 200, first.content
    switch(space, "shop.receipts", on=False)
    off = client(actor).get(path)
    assert (off.status_code, off.json()["code"]) == (404, "feature_off")
    switch(space, "shop.receipts")
    uninstall_module(space, "shop")
    removed = client(actor).get(path)
    assert (removed.status_code, removed.json()["code"]) == (404, "shop_closed")
    install_module(space, "shop")
    space.refresh_from_db()
    receipts_off = client(actor).get(path)
    assert (receipts_off.status_code, receipts_off.json()["code"]) == (404, "feature_off")
    switch(space, "shop.receipts")
    restored = client(actor).get(path)
    assert restored.status_code == 200
    assert restored.json() == first.json()
    payment = payment_for(order)
    assert ManualSettlement.objects.filter(payment=payment, method="upi", reference="UTR-cx4").count() == 1
    assert ShopOrder.objects.filter(pk=order.pk, status="collected").count() == 1


def test_email_receipt_saves_a_guest_address_once_and_audits_no_address(monkeypatch):
    space, actor, order = sale("cx4-shop-email")
    notice = Mock(return_value=True)
    monkeypatch.setattr("apps.shop.notices.buyer_notice", notice)
    assert email_receipt(order, "guest@example.test", actor=actor) is True
    assert email_receipt(order, "replacement@example.test", actor=actor) is True
    order.refresh_from_db()
    assert order.guest_email == "guest@example.test"
    assert list(AuditLog.objects.filter(makerspace=space, action="shop.receipt_emailed").order_by("pk")
                .values_list("meta", flat=True)) == [{"guest_email_saved": True}, {"guest_email_saved": False}]
    assert notice.call_count == 2
    assert receipt_payload(order)["method"] == "upi"
    assert receipt_payload(order)["paid"] is True


def test_shop_webhook_insert_failure_is_safe_and_shop_off_does_not_dispatch(monkeypatch):
    space, actor, order = sale("cx4-shop-webhook")
    NotificationPreference.objects.update_or_create(makerspace=space, feature="payments", channel="webhook",
                                                    defaults={"enabled": True})
    dispatch = Mock(side_effect=RuntimeError("destination unavailable"))
    monkeypatch.setattr("apps.integrations.dispatch_channels.dispatch_channel", dispatch)
    assert order_webhook(order, "shop_order_ready_for_pickup") is False
    dispatch.assert_called_once()
    order.refresh_from_db()
    assert order.status == "collected"
    assert ManualSettlement.objects.filter(payment=payment_for(order)).count() == 1
    uninstall_module(space, "shop")
    order.makerspace = space
    assert order_webhook(order, "shop_order_ready_for_pickup") is False
    assert dispatch.call_count == 1
    install_module(space, "shop")
    order.makerspace = space
    dispatch.side_effect = None
    assert order_webhook(order, "shop_order_ready_for_pickup") is True
    assert dispatch.call_count == 2
