"""Shared fixtures for the lane L24 tests (local, untracked)."""

from decimal import Decimal

from apps.audit.models import AuditLog
from apps.payments.models import RefundCase
from tests.payments.refund_case_helpers import space_with_currency
from tests.return_helpers import authenticated_client, make_member

FEATURE = "charges.price_drop_refunds"
D = Decimal
CHARGES = ("charges.enabled", "charges.bookings", "charges.events", "charges.machines", "charges.membership",
           "charges.pricing")


def setup(space, *, on=True, modules=(), features=()):
    space.enabled_modules = sorted(set(space.enabled_modules or []) | set(modules))
    wanted = set(space.enabled_features or []) | set(CHARGES) | set(features)
    wanted = wanted | {FEATURE} if on else wanted - {FEATURE}
    space.enabled_features = sorted(wanted)
    space.save(update_fields=["enabled_modules", "enabled_features", "updated_at"])
    return space


def l24_space(slug, *, on=True, modules=(), features=()):
    space = setup(space_with_currency(slug), on=on, modules=modules, features=features)
    return space, make_member(f"{slug}-sm", space)


def client(user):
    return authenticated_client(user)


def preview(response):
    assert response.status_code == 200, getattr(response, "data", response)
    return response.data["price_drop"]


def cases(**filters):
    return list(RefundCase.objects.filter(**filters).order_by("pk"))


def opened_rows(area=None):
    rows = AuditLog.objects.filter(action="pricing.price_drop_refunds_opened")
    return [row for row in rows if area is None or row.meta.get("area") == area]
