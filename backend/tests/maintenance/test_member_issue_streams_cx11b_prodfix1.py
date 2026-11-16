"""534: personal issue history omits only disabled streams and keeps owner scoping."""
import pytest

from apps.bookings.models import Booking
from apps.maintenance.models import IssueReport
from apps.maintenance.repairs import services_issues as svc
from tests.maintenance.l16_helpers import tomorrow, world
from tests.maintenance.report_world_cx11b_g3 import report_world
from tests.maintenance.route_support_cx11b_g3 import send
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.return_helpers import make_member

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_bookings]


def loan_report(w):
    return svc.file_report(w.space, reporter=w.person, source="loan", origin=w.origin,
                           subject_type=w.kind, subject=w.subject, title="My retained loan report",
                           description="Private loan description", validated=[])


def room_report(w, person, title):
    start, end = tomorrow()
    booking = Booking.objects.create(space=w.room, member=person, starts_at=start, ends_at=end,
                                     status="confirmed", name="Booker", email=person.email)
    return svc.file_report(w.space, reporter=person, source="booking", origin=booking,
                           subject_type="bookable_space", subject=w.room, title=title,
                           description="Private room description", validated=[])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.issue_reporting", "loans.enabled"])
@pytest.mark.parametrize("scoped", [False, True], ids=["all-spaces", "one-space"])
def test_disabling_one_history_stream_keeps_enabled_streams_and_the_same_rows(native, key, scoped):
    w = report_world("loan", native)
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {"bookings.issue_reporting"})
    w.space.save(update_fields=["enabled_features"])
    loan = loan_report(w)
    room = room_report(w, w.person, "My enabled room report")
    other = world("prodfix1-history-other")
    foreign_owned = room_report(other, w.person, "My other-space report")
    stranger = make_member("prodfix1-history-stranger", w.space, membership_role="member", role="requester")
    foreign_owner = room_report(w, stranger, "Someone else's private report")
    ids = [loan.pk, room.pk, foreign_owned.pk, foreign_owner.pk]
    before = list(IssueReport.objects.filter(pk__in=ids).order_by("pk").values_list("pk", "state", "title"))
    params = {"makerspace": w.space.pk} if scoped else {}

    def history(expected):
        with no_domain_writes():
            response = send(w.client, "member-issues", [], body=params)
        assert response_pair(response) == (200, None)
        assert sorted(row["id"] for row in response.data) == sorted(expected)
        assert all("description" not in row and "reporter_email" not in row for row in response.data)
        assert list(IssueReport.objects.filter(pk__in=ids).order_by("pk").values_list("pk", "state", "title")) == before

    kept = [room.pk] if scoped else [room.pk, foreign_owned.pk]
    history([loan.pk, *kept])
    original = switch(w.space, key)
    history(kept)
    switch(w.space, key, original=original)
    history([loan.pk, *kept])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_personal_history_keeps_a_live_repair_stream_when_reporting_is_off(native):
    w = report_world("loan", native)
    row = loan_report(w)
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {"inventory.repairs"})
    w.space.save(update_fields=["enabled_features"])
    switch(w.space, "inventory.issue_reporting")

    def history(expected):
        with no_domain_writes():
            response = send(w.client, "member-issues", [])
        assert response_pair(response) == (200, None)
        assert [item["id"] for item in response.data] == expected
        assert IssueReport.objects.get(pk=row.pk).title == "My retained loan report"

    history([row.pk])
    original = switch(w.space, "inventory.repairs")
    history([])
    switch(w.space, "inventory.repairs", original=original)
    history([row.pk])
