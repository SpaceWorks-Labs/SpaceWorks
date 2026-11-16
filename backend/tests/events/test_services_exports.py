"""The service split must keep existing quota and occupancy callers working."""

from apps.events import capacity, services, services_event_details
from apps.events.models import EventRegistration
from apps.makerspaces import limits


def test_service_barrel_preserves_quota_module_used_by_existing_callers(monkeypatch):
    assert services.limits is limits
    assert services.limits is services_event_details.limits
    calls = []
    monkeypatch.setattr(
        services.limits, "check_quota",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    space = object()
    services_event_details.limits.check_quota(space, "events", adding=1)
    assert calls == [((space, "events"), {"adding": 1})]


def test_service_barrel_preserves_canonical_confirmed_statuses():
    assert services.CONFIRMED_STATUSES is capacity.CONFIRMED_STATUSES
    assert services.CONFIRMED_STATUSES == (
        EventRegistration.Status.REGISTERED,
        EventRegistration.Status.ATTENDED,
    )
