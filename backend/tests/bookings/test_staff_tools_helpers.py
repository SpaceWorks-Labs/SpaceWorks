"""Stable clocks and real workflows shared by BK-B service/API tests."""

from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

from django.utils import timezone

from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.bookings import services
from apps.bookings.models import Booking
from apps.payments.models import Payment
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

NOW = datetime(2030, 1, 7, 10, tzinfo=dt_timezone.utc)
QUESTIONS = [{"id": "purpose", "label": "Purpose", "type": "short_text", "options": [], "required": True}]


def world(monkeypatch, *, status="confirmed", charged=False, permission="manage_reservations"):
    monkeypatch.setattr(timezone, "now", lambda: NOW)
    monkeypatch.setattr("apps.bookings.notifications.notify_booking_status", lambda *args, **kwargs: None)
    tenant, actor, grantee, resource, grant, member = grant_fixture(permission, slug="staff-tools")
    tenant.enabled_features = sorted(set(tenant.enabled_features) | {
        "bookings.staff_tools", "bookings.clone", "charges.enabled", "charges.bookings",
    })
    tenant.timezone = "UTC"
    tenant.save(update_fields=["enabled_features", "timezone"])
    resource.approval_mode = "instant" if status == "confirmed" else "approve"
    resource.custom_form = QUESTIONS
    resource.payment_amount = 12 if charged else 0
    resource.save(update_fields=["approval_mode", "custom_form", "payment_amount"])
    row = services.create_booking(resource, member=member, starts_at=NOW + timedelta(days=2),
                                  ends_at=NOW + timedelta(days=2, hours=1), note="Original note",
                                  custom_answers={"purpose": "Original answer"})
    return SimpleNamespace(tenant=tenant, actor=actor, grantee=grantee, resource=resource,
                           grant=grant, member=member, row=row, client=client_for(grantee))


def reserve(w, *, starts_at=None, **values):
    start = starts_at or NOW + timedelta(days=4)
    return services.create_booking(w.resource, member=w.member, starts_at=start,
                                   ends_at=start + timedelta(hours=1), custom_answers={"purpose": "Other"}, **values)


def snapshot(w):
    return (
        Booking.objects.filter(pk=w.row.pk).values().get(),
        list(Payment.objects.filter(makerspace=w.tenant).order_by("pk").values()),
        list(AuditLog.objects.filter(makerspace=w.tenant).order_by("pk").values()),
    )


def url(w, operation):
    if operation == "clone":
        return f"/api/v1/admin/spaces/{w.resource.pk}/clone/"
    suffix = {"details": "details", "time": "time", "restore": "restore"}[operation]
    return f"/api/v1/admin/bookings/{w.row.pk}/{suffix}/"


def payload(operation):
    if operation == "details":
        return {"note": "Updated note"}
    if operation == "time":
        start = NOW + timedelta(days=3)
        return {"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}
    return {}


def request(w, operation, client=None, **extra):
    client = client or w.client
    method = client.patch if operation == "details" else client.post
    return method(url(w, operation), {**payload(operation), **extra}, format="json")


def full_manager(w):
    # Fixed roles: built-in rows are never widened; promote this person instead.
    from tests.fixed_roles.helpers import assign_builtin_roles
    assign_builtin_roles(w.actor, w.tenant, "space_manager")
    return w.actor
