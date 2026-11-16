from datetime import timedelta
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.profile_activity_public import daily_activity
from apps.makerspaces.profile_activity_sources import activity_sources

from .conftest import enable, graph, make_event, request_row, return_row

pytestmark = pytest.mark.django_db


def test_sources_registered_with_independent_consent(published, moment, monkeypatch):
    registered = {source.family: source for source in activity_sources()}
    assert {"speaking", "loans", "bookings"} <= registered.keys()
    for family, consent in [("speaking", "show_speaking"), ("loans", "show_loans"), ("bookings", "show_bookings")]:
        def refuse(*args):
            raise AssertionError("Family queried without consent")
        from apps.makerspaces import profile_activity_sources as registry
        from apps.makerspaces.profile_activity_sources import ActivitySource
        monkeypatch.setattr(registry, "_sources", {family: ActivitySource(family, registered[family].module, refuse)})
        assert graph(published, moment)["families"] == {}
        enable(published, **{consent: True}, show_activity_graph=False)
        assert daily_activity(published, {})["days"] == []
        enable(published, **{consent: False}, show_activity_graph=True)


def test_speaking_is_owned_scoped_published_past_and_deduplicated(published, moment, speaker_source):
    enable(published, show_speaking=True)
    event = make_event(published, moment)
    speaker_source.rows.extend([
        SimpleNamespace(event=event, occurred_at=moment, role="speaker"),
        SimpleNamespace(event=event, occurred_at=moment + timedelta(minutes=1), role="speaker"),
        SimpleNamespace(event=make_event(published, moment, is_public=False), occurred_at=moment, role="speaker"),
        SimpleNamespace(event=make_event(published, moment, status="draft"), occurred_at=moment, role="speaker"),
        SimpleNamespace(event=event, occurred_at=timezone.now() + timedelta(days=1), role="speaker"),
    ])
    assert graph(published, moment)["families"] == {"speaking": 1}
    assert speaker_source.calls == [(published.membership.user_id, published.membership.makerspace_id)]
    event.status = "completed"; event.save()
    assert graph(published, moment)["count"] == 0  # explicit PUBLISHED-only contract
    event.status = "published"; event.save()
    speaker_source.rows.clear()  # corrected/unlinked/purged contributions vanish immediately
    assert graph(published, moment)["count"] == 0


def test_speaking_missing_parallel_seam_is_empty(published, moment, speaker_source, monkeypatch):
    enable(published, show_speaking=True)
    del speaker_source.module.contributions_for
    assert graph(published, moment)["count"] == 0
    monkeypatch.setitem(sys.modules, "apps.events.speaker_history", None)
    assert graph(published, moment)["count"] == 0


def test_speaking_disabled_host_is_hidden(published, moment, speaker_source, other_space):
    enable(published, show_speaking=True)
    event = make_event(published, moment, makerspace=other_space)
    speaker_source.rows.append(SimpleNamespace(event=event, occurred_at=moment, role="speaker"))
    assert graph(published, moment)["count"] == 1
    other_space.enabled_modules = []; other_space.save()
    assert graph(published, moment)["count"] == 0


def test_loans_use_explicit_owner_tenant_and_physical_loan_identity(published, moment, other_user, other_space, monkeypatch):
    from apps.hardware_requests.models import PublicToolLoan
    enable(published, show_loans=True)
    request_row(published, moment)
    request_row(published, moment, requester=other_user)
    request_row(published, moment, makerspace=other_space)
    request_row(published, moment, status="accepted")
    for source in ("admin_direct", "public_self_checkout"):
        backing = request_row(published, moment)
        with monkeypatch.context() as patch:
            patch.setattr(timezone, "now", lambda: moment)
            PublicToolLoan.objects.create(makerspace=published.membership.makerspace, request=backing,
                requester=published.membership.user, target_type="product", target_id=1,
                target_label="Private hardware", source=source)
    assert graph(published, moment) == {"date": moment.astimezone(
        ZoneInfo("Asia/Kolkata")).date(), "count": 3, "families": {"loans": 3}}
    assert "Private hardware" not in str(graph(published, moment))


def test_loans_returns_dedup_by_loan_day_and_live_status(published, moment, monkeypatch):
    from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
    enable(published, show_loans=True)
    reviewed = request_row(published, moment - timedelta(days=2), status="returned")
    with monkeypatch.context() as patch:
        patch.setattr(timezone, "now", lambda: moment)
        return_row(published, reviewed)
        return_row(published, reviewed)  # two partial returns on one day: one loan/day
        backing = request_row(published, moment, status="returned")
        direct = PublicToolLoan.objects.create(makerspace=published.membership.makerspace, request=backing,
            requester=published.membership.user, target_type="product", target_id=1, target_label="Private tool",
            status="returned", returned_at=moment + timedelta(minutes=5))
    assert graph(published, moment)["count"] == 2
    HardwareRequest.objects.filter(pk=reviewed.pk).update(status="accepted")
    assert graph(published, moment)["count"] == 1
    # A changed owner cannot retain a previous person's history.
    PublicToolLoan.objects.filter(pk=direct.pk).update(requester=User.objects.create_user(username="replacement-owner"))
    assert graph(published, moment)["count"] == 0


def make_booking(profile, moment, **kwargs):
    from apps.bookings.models import BookableSpace, Booking
    resource = BookableSpace.objects.create(makerspace=kwargs.pop("makerspace", profile.membership.makerspace),
                                           name="Private resource")
    values = dict(space=resource, member=profile.membership.user, name="Private borrower",
                  email="private@example.test", phone="1234", starts_at=moment,
                  ends_at=moment + timedelta(hours=1), status="completed")
    values.update(kwargs)
    return Booking.objects.create(**values)


def test_bookings_only_completed_or_arrived_and_explicit_owned(published, moment, other_user, other_space):
    enable(published, show_bookings=True)
    make_booking(published, moment)
    make_booking(published, moment, member=other_user)
    make_booking(published, moment, member=None)  # same free-text contact grants nothing
    make_booking(published, moment, makerspace=other_space)
    make_booking(published, moment, status="confirmed")
    make_booking(published, timezone.now() + timedelta(days=1))
    assert graph(published, moment)["families"] == {"bookings": 1}
    assert "Private" not in str(graph(published, moment))


def test_booking_arrival_reversal_and_completion_same_day_dedup(published, moment):
    from apps.bookings.models import Booking
    enable(published, show_bookings=True)
    booking = make_booking(published, moment, status="confirmed", arrived_at=moment)
    assert graph(published, moment)["count"] == 1
    Booking.objects.filter(pk=booking.pk).update(arrived_at=None)
    assert graph(published, moment)["count"] == 0
    Booking.objects.filter(pk=booking.pk).update(status="completed", arrived_at=moment)
    assert graph(published, moment)["count"] == 1
    Booking.objects.filter(pk=booking.pk).update(status="cancelled", arrived_at=None)
    assert graph(published, moment)["count"] == 0


@pytest.mark.parametrize("family,flag,module", [
    ("speaking", "show_speaking", "events"), ("loans", "show_loans", "request_workflow"),
    ("bookings", "show_bookings", "bookings"),
])
def test_module_gate_precedes_source_execution(published, moment, monkeypatch, family, flag, module):
    from apps.makerspaces import profile_activity_sources as registry
    from apps.makerspaces.profile_activity_sources import ActivitySource
    enable(published, **{flag: True})
    def refuse(*args):
        raise AssertionError("A disabled module was queried")
    monkeypatch.setattr(registry, "_sources", {family: ActivitySource(family, module, refuse)})
    space = published.membership.makerspace
    space.enabled_modules = ["membership"]; space.save()
    assert graph(published, moment)["count"] == 0
