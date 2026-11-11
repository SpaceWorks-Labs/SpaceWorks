"""Cancellation undo must reacquire a managed active-booking slot."""

from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError

from apps.bookings import services
from apps.makerspaces import limits
from tests.bookings.test_staff_tools_helpers import reserve, snapshot, world

pytestmark = pytest.mark.django_db


def managed_world(monkeypatch, settings, status):
    settings.PLATFORM_DOMAIN_SUFFIX = "spaces.example.test"
    # Decision 236: MANAGED_RESOURCE_LIMITS only suggests; the limit that binds is the space's override.
    w = world(monkeypatch, status=status)
    w.tenant.resource_limit_overrides = {"bookings": 1}
    w.tenant.save(update_fields=["resource_limit_overrides"])
    return w


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_restore_refuses_slot_taken_during_undo_window(
    monkeypatch, settings, django_capture_on_commit_callbacks, status,
):
    w = managed_world(monkeypatch, settings, status)
    w.row = services.cancel_booking(w.row, actor=w.grantee)
    replacement = reserve(w)
    assert replacement.status == status
    assert limits._bookings(w.tenant) == 1
    before = snapshot(w)
    notify = Mock()
    monkeypatch.setattr("apps.bookings.notifications.notify_booking_status", notify)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        with pytest.raises(ValidationError) as failure:
            services.restore_booking(w.row, actor=w.grantee)

    assert failure.value.get_codes() == {"limit": "limit_reached"}
    assert snapshot(w) == before
    assert limits._bookings(w.tenant) == 1
    replacement.refresh_from_db()
    assert replacement.status == status
    notify.assert_not_called()
    assert callbacks == []


@pytest.mark.parametrize("status", ["pending", "confirmed"])
@pytest.mark.parametrize("rebooked", [False, True])
def test_restore_succeeds_when_managed_slot_is_free(monkeypatch, settings, status, rebooked):
    w = managed_world(monkeypatch, settings, status)
    w.row = services.cancel_booking(w.row, actor=w.grantee)
    if rebooked:
        replacement = reserve(w)
        services.cancel_booking(replacement, actor=w.grantee)
    assert limits._bookings(w.tenant) == 0

    restored = services.restore_booking(w.row, actor=w.grantee)

    assert restored.status == status
    assert restored.cancelled_at is None and restored.status_before_cancel == ""
    assert limits._bookings(w.tenant) == 1


@pytest.mark.parametrize("status", ["pending", "confirmed"])
@pytest.mark.parametrize("mode", ["self_host", "unlimited"])
def test_restore_preserves_unlimited_and_self_host_behavior(monkeypatch, settings, status, mode):
    w = managed_world(monkeypatch, settings, status)
    w.row = services.cancel_booking(w.row, actor=w.grantee)
    reserve(w)
    if mode == "self_host":
        settings.PLATFORM_DOMAIN_SUFFIX = ""
    else:
        w.tenant.resource_limit_overrides = {"bookings": None}
        w.tenant.save(update_fields=["resource_limit_overrides"])
    assert limits.resource_limit(w.tenant, "bookings") is None

    restored = services.restore_booking(w.row, actor=w.grantee)

    assert restored.status == status
    assert limits._bookings(w.tenant) == 2
