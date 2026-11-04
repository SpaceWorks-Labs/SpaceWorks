"""`?price_drop_preview=1` on a price-saving endpoint: what the save WOULD refund (#163A).

The decorated view runs exactly as a real save -- same permissions, validation, locks and
price arithmetic -- inside a transaction that is always rolled back. While it runs, the
price-change hook (`hook.on_price_change`) collects the affected items here instead of
opening cases, so the preview and the save can never disagree. Audit rows, notices and
on-commit work queued by the save are rolled back with it.

With `charges.price_drop_refunds` off the preview answers 404, like any switched-off
surface. A save that changes no price previews an empty list.
"""

from contextvars import ContextVar
from functools import wraps

from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

PARAM = "price_drop_preview"
LIMIT = 200
_ACTIVE = ContextVar("price_drop_preview", default=None)

PREVIEW_PARAMETER = OpenApiParameter(
    PARAM, OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False,
    description="Preview only (needs `charges.price_drop_refunds`): run the save, roll it back, and return "
                "`{price_drop: {items, count, truncated, totals}}` -- the paid, not-yet-used items whose price "
                "would drop and the difference a refund case would open for. 404 while the switch is off.",
)


class PreviewUnavailable(NotFound):
    default_detail = "Price-drop refunds are not switched on in this makerspace."
    default_code = "price_drop_disabled"


class _Rollback(Exception):
    pass


class Collector:
    def __init__(self):
        self.items = []

    def report(self):
        totals = {}
        for row in self.items:
            totals[row.payment.currency] = totals.get(row.payment.currency, 0) + row.difference
        return {"count": len(self.items), "truncated": len(self.items) > LIMIT,
                "items": [row.as_json() for row in self.items[:LIMIT]],
                "totals": [{"currency": currency, "difference": str(amount)}
                           for currency, amount in sorted(totals.items())]}


def active_collector():
    return _ACTIVE.get()


def wants_preview(request):
    return str(request.query_params.get(PARAM, "")).lower() in ("1", "true", "yes")


def previewable(method):
    """Wrap a price-saving APIView method so `?price_drop_preview=1` dry-runs it."""
    @wraps(method)
    def wrapper(self, request, *args, **kwargs):
        if not wants_preview(request):
            return method(self, request, *args, **kwargs)
        collector = Collector()
        token = _ACTIVE.set(collector)
        response = None
        try:
            with transaction.atomic():
                response = method(self, request, *args, **kwargs)
                raise _Rollback()
        except _Rollback:
            pass
        finally:
            _ACTIVE.reset(token)
        if response is not None and getattr(response, "status_code", 200) >= 400:
            return response
        return Response({"price_drop": collector.report()})
    return wrapper
