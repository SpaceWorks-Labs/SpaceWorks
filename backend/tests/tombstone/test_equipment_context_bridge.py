"""Run in a freshly started tombstone profile, never an override_settings simulation."""
import pytest
from django.http import Http404

from apps.separability.equipment_context_bridge import observe_booking, observe_event
from apps.separability.registry import runtime_active


def test_tombstoned_selected_domains_fail_without_querying_retained_models():
    inactive = [name for name in ("events", "bookings") if not runtime_active(name)]
    assert inactive, "This test requires a fresh events and/or bookings tombstone profile"
    if "events" in inactive:
        with pytest.raises(Http404):
            observe_event(1, 1)
    if "bookings" in inactive:
        with pytest.raises(Http404):
            observe_booking(1, 1)
