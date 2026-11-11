from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.bookings.services_departure import record_departure
from apps.operations.views_dashboard_counts import build_dashboard
from tests.modules.family_helpers import account, family_space

pytestmark = pytest.mark.django_db


def _issue(space, *, name):
    member = account(name)
    start = timezone.now() - timedelta(hours=2)
    room = BookableSpace.objects.create(makerspace=space, name=f"Room {name}")
    booking = Booking.objects.create(space=room, member=member, name=name, email=member.email, phone=member.phone,
        starts_at=start, ends_at=start + timedelta(hours=1), status="confirmed", arrived_at=start)
    record_departure(booking, actor=member, outcome="damaged", remark="Table leg broke", source="member")
    return booking.issues.get()


def test_open_booking_issues_counts_only_this_tenants_unresolved_issues():
    space = family_space("issue-count", "bookings")
    other = family_space("issue-count-other", "bookings")
    open_issue = _issue(space, name="issue-open")
    resolved = _issue(space, name="issue-resolved")
    resolved.resolved_at = timezone.now()
    resolved.save(update_fields=["resolved_at"])
    _issue(other, name="issue-other")

    counts = build_dashboard(space)

    assert counts["open_booking_issues"] == 1
    assert open_issue.resolved_at is None


def test_open_booking_issues_absent_when_bookings_family_is_off():
    space = family_space("issue-count-off", "events")

    assert build_dashboard(space).get("open_booking_issues", 0) == 0
