"""Cash-up (`shop.cash_up`, Q-S8/Q-S19): open with a float, close with the counted cash.

Expected cash = the opening float + cash taken for this session's sales (their effective
desk receipts) - shop cash refunds handed back while the session was open. The variance is
counted - expected. With `billing.maker_checker` on, closing is a proposal and a SECOND
person holding `manage_shop` (or `record_payment`) confirms it (#128 C-5, Q-S19); otherwise
the close is final. Every step is audited; a closed session is frozen.
"""

from django.utils.translation import gettext
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .errors import ShopRefused
from .gates import write_allowed
from .models import ShopCashSession


def _currency(space):
    from apps.payments.models import MakerspacePaymentSettings
    return MakerspacePaymentSettings.for_makerspace(space).default_currency


@transaction.atomic
def open_cash(space, *, actor, opening_float):
    from apps.makerspaces.guards import require_module_locked

    space = require_module_locked(space, "shop")
    write_allowed(space)
    if ShopCashSession.objects.filter(makerspace=space).exclude(status=ShopCashSession.Status.CLOSED).exists():
        raise ShopRefused("cash_session_open", gettext("A cash session is already open; close it first."))
    session = ShopCashSession.objects.create(makerspace=space, currency=_currency(space),
                                             opening_float=Decimal(opening_float), opened_by=actor)
    audit.record(actor, "shop.cash_session_opened", makerspace=space, target=session,
                 meta={"session_id": session.pk, "opening_float": str(session.opening_float)})
    return session


def expected_cash(session, *, until=None):
    from apps.payments.models import ManualSettlement, Refund

    until = until or timezone.now()
    receipts = ManualSettlement.objects.filter(
        payment__subject_type="shop_order", payment__makerspace_id=session.makerspace_id,
        payment__subject_id__in=session.orders.values("pk"), method="cash", amended_by__isnull=True,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    refunds = Refund.objects.filter(
        payment__subject_type="shop_order", payment__makerspace_id=session.makerspace_id, method="cash",
        status=Refund.Status.SUCCEEDED, amended_by__isnull=True, created_at__gte=session.opened_at,
        created_at__lte=until,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return session.opening_float + receipts - refunds, receipts, refunds


def _finish(session, actor):
    session.status, session.closed_at, session.confirmed_by = ShopCashSession.Status.CLOSED, timezone.now(), actor
    session.save(update_fields=["status", "closed_at", "confirmed_by"])
    audit.record(actor, "shop.cash_session_closed", makerspace=session.makerspace, target=session, meta={
        "session_id": session.pk, "expected": str(session.expected_cash), "counted": str(session.counted_cash),
        "variance": str(session.variance), "checked_by_second_person": session.confirmed_by_id != session.closed_by_id})
    return session


@transaction.atomic
def close_cash(session, *, actor, counted_cash, note=""):
    session = ShopCashSession.objects.select_for_update().select_related("makerspace").get(pk=session.pk)
    if session.status != ShopCashSession.Status.OPEN:
        raise ShopRefused("cash_session_closed", gettext("This cash session is not open."))
    now = timezone.now()
    expected, _receipts, _refunds = expected_cash(session, until=now)
    counted = Decimal(counted_cash)
    session.counted_cash, session.expected_cash, session.variance = counted, expected, counted - expected
    session.note, session.closed_by, session.closing_at = (note or "")[:300], actor, now
    session.status = ShopCashSession.Status.CLOSING
    session.save(update_fields=["counted_cash", "expected_cash", "variance", "note", "closed_by", "closing_at",
                                "status"])
    if feature_enabled(session.makerspace, "billing.maker_checker"):
        audit.record(actor, "shop.cash_session_close_proposed", makerspace=session.makerspace, target=session,
                     meta={"session_id": session.pk, "variance": str(session.variance)})
        return session
    return _finish(session, actor)


@transaction.atomic
def confirm_cash(session, *, actor):
    session = ShopCashSession.objects.select_for_update().select_related("makerspace").get(pk=session.pk)
    if session.status != ShopCashSession.Status.CLOSING:
        raise ShopRefused("cash_session_check", gettext("This cash session is not waiting for a second check."))
    if session.closed_by_id == getattr(actor, "pk", None):
        raise ShopRefused("cash_session_check", gettext("A second person must confirm the cash-up."))
    space_id = session.makerspace_id
    if not (rbac.can(actor, rbac.Action.MANAGE_SHOP, space_id) or rbac.can(actor, rbac.Action.RECORD_PAYMENT,
                                                                            space_id)):
        raise ShopRefused("cash_session_check", gettext("Only a shop manager or finance staff can confirm a cash-up."))
    return _finish(session, actor)
