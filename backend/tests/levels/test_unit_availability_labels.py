"""Unit level: the public availability rule from CLAUDE.md, pinned at every boundary with no database.

available <= 0 or total <= 0 -> Unavailable; available <= ceil(total * 0.2) -> Limited; else Available.
`exact_count` shows a number only when show_public_count is true; `hidden` shows nothing.
"""
from types import SimpleNamespace

import pytest

from apps.inventory.models import PublicAvailabilityMode
from apps.inventory.public_availability import EVENT_ONLY_LABEL, _status_label, get_public_availability


def _product(available, total, mode=PublicAvailabilityMode.STATUS_ONLY, show=False, event_only=False):
    return SimpleNamespace(available_quantity=available, total_quantity=total, public_availability_mode=mode,
                           show_public_count=show, event_only=event_only)


@pytest.mark.parametrize("available,total,label", [
    (0, 10, "Unavailable"), (-1, 10, "Unavailable"), (5, 0, "Unavailable"), (0, 0, "Unavailable"),
    (1, 10, "Limited"), (2, 10, "Limited"),      # ceil(10 * 0.2) == 2 is the last Limited
    (3, 10, "Available"),
    (1, 1, "Limited"), (1, 3, "Limited"), (2, 3, "Available"),   # ceil(0.6) == 1
    (1, 5, "Limited"), (2, 5, "Available"),                      # ceil(1.0) == 1
    (6, 30, "Limited"), (7, 30, "Available"),
    (100, 100, "Available"),
])
def test_status_label_boundaries(available, total, label):
    assert _status_label(_product(available, total)) == label


def test_hidden_mode_returns_nothing():
    assert get_public_availability(_product(5, 10, PublicAvailabilityMode.HIDDEN)) is None


def test_status_only_never_carries_a_count():
    assert get_public_availability(_product(5, 10, PublicAvailabilityMode.STATUS_ONLY, show=True)) == {
        "mode": "status_only", "label": "Available"}


def test_exact_count_needs_the_safety_gate():
    shown = get_public_availability(_product(2, 10, PublicAvailabilityMode.EXACT_COUNT, show=True))
    gated = get_public_availability(_product(2, 10, PublicAvailabilityMode.EXACT_COUNT, show=False))
    assert shown == {"mode": "exact_count", "count": 2, "label": "Limited"}
    assert gated == {"mode": "status_only", "label": "Limited"}


def test_event_only_items_show_a_neutral_label_even_in_exact_mode():
    got = get_public_availability(_product(2, 10, PublicAvailabilityMode.EXACT_COUNT, show=True, event_only=True))
    assert got == {"mode": "status_only", "label": EVENT_ONLY_LABEL}
