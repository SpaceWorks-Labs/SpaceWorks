from datetime import timedelta

from django.utils import timezone
import pytest

from apps.events.models import EventRegistration
from apps.events.models_attendance import EventCheckInEvent
from apps.events.programme.live import project_live
from apps.events.programme.providers import Respondent
from apps.operations import reports_events_programme as funnel
from tests.events.staff_grant_helpers import grant_fixture


def registration(event, member, status):
    return EventRegistration.objects.create(event=event, member=member, name=member.display_name,
        email=member.email, phone=member.phone, status=status)


@pytest.mark.django_db
def test_live_deduplicates_rechecks_and_excludes_undone_attendance():
    space, manager, member, event, _ = grant_fixture("check_in")
    now = timezone.now()
    event.starts_at, event.ends_at = now - timedelta(hours=1), now + timedelta(hours=1)
    event.save(update_fields=["starts_at", "ends_at"])
    attended = registration(event, member, "attended")
    for minutes in (50, 20):
        EventCheckInEvent.objects.create(makerspace=space, event=event, registration=attended,
            actor=manager, source="online", attended_at=now - timedelta(minutes=minutes))
    from tests.events.ticketing_helpers import account
    undone = registration(event, account("undone"), "registered")
    EventCheckInEvent.objects.create(makerspace=space, event=event, registration=undone,
        actor=manager, source="online", attended_at=now - timedelta(minutes=10))
    result = project_live(event, actor=member, now=now)
    assert result["checked_in"] == 1
    assert result["going"] == 2
    assert sum(bucket["count"] for bucket in result["arrivals"]) == 1
    assert result["active"] and not result["first_run"]


@pytest.mark.django_db
def test_funnel_dedupes_application_and_registration_and_caps_ratios(monkeypatch):
    _, manager, member, event, _ = grant_fixture()
    now = timezone.now()
    registration(event, member, "attended")
    monkeypatch.setattr(funnel, "application_respondents", lambda **kwargs: (
        True, [Respondent(("member", member.pk), now - timedelta(days=2)),
               Respondent(("member", member.pk), now - timedelta(days=1))]))
    result = funnel.project_funnel(event, actor=manager, now=now + timedelta(seconds=1))
    assert [stage["count"] for stage in result["stages"]] == [1, 1, 1, 0]
    assert result["stages"][1]["percent"] == 100
    assert len(result["timeline"]) == 14
    assert sum(day["count"] for day in result["timeline"]) == 1
    assert funnel.percentage(2, 1) == 100
    assert funnel.percentage(0, 0) is None


@pytest.mark.django_db
def test_timeline_comparison_uses_tenant_dates_not_utc(monkeypatch):
    _, _, member, event, _ = grant_fixture()
    event.timezone_name = "Asia/Kolkata"
    row = registration(event, member, "registered")
    from datetime import UTC, datetime
    instant = datetime(2026, 10, 17, 20, 0, tzinfo=UTC)
    EventRegistration.objects.filter(pk=row.pk).update(created_at=instant)
    monkeypatch.setattr(funnel, "application_respondents", lambda **kwargs: (False, ()))
    result = funnel.project_funnel(event, now=instant + timedelta(hours=1))
    assert result["timeline"][-1]["date"] == "2026-10-18"
    assert result["timeline"][-1]["count"] == 1
