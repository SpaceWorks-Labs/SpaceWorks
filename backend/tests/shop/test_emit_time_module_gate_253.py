"""Decision 253(a): shop notices check the shop module when they are emitted, not only at delivery."""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.shop import notices

from .helpers import module_off, product, shop_manager, shop_space
from .test_hold_return_refund_coordination import _paid_online

pytestmark = pytest.mark.django_db(transaction=True)


def _order(slug):
    space = shop_space(slug, "shop.online", "shop.holds")
    seller = shop_manager(space)
    _row, variant = product(space, seller, stock=3)
    return space, _paid_online(space, variant, qty=1, buyer=f"{slug}-buyer")


def _count(space):
    return NotificationEnvelope.objects.filter(makerspace=space, source_kind__in=[notices.SOURCE, notices.STOCK_SOURCE]).count()


def test_staff_notice_writes_no_envelope_while_shop_is_off():
    space, order = _order("t253-shop-staff")
    module_off(space)
    before = _count(space)
    assert not notices.staff_notice(space, order, "shop_order_new")
    assert _count(space) == before


def test_buyer_notice_writes_no_envelope_while_shop_is_off():
    space, order = _order("t253-shop-buyer")
    module_off(space)
    before = _count(space)
    assert notices.buyer_notice(order, "shop_order_ready") is None
    assert _count(space) == before


def test_staff_notice_still_emits_while_shop_is_on():
    space, order = _order("t253-shop-on")
    assert notices.staff_notice(space, order, "shop_order_new") is True
    assert NotificationEnvelope.objects.filter(makerspace=space, event="shop_order_new").exists()
