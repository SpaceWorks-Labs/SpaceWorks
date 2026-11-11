"""Open item A16: the staff sessions list filters by machine type, machine, member and source."""

import pytest

from tests.machines.session_helpers import open_session, session_world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _ids(response):
    assert response.status_code == 200, response.content
    return {row["id"] for row in response.json()["results"]}


def test_machine_type_filter_narrows_and_an_unknown_type_returns_nothing():
    w = session_world("a16-type")
    first = open_session(w)
    second = open_session(w, machine=w.machines[1], member=None, source="device")
    staff = authenticated_client(w.staff)
    base = f"/api/v1/admin/makerspaces/{w.space.pk}/machine-sessions"
    type_id = w.machines[0].machine_type_id
    assert _ids(staff.get(f"{base}?machine_type={type_id}")) == {first.pk, second.pk}
    assert _ids(staff.get(f"{base}?machine_type=999999")) == set()
    # A non-numeric value is ignored rather than a 500.
    assert _ids(staff.get(f"{base}?machine_type=abc")) == {first.pk, second.pk}


def test_machine_member_and_source_filters_combine():
    w = session_world("a16-combo")
    first = open_session(w)
    second = open_session(w, machine=w.machines[1], member=None, source="device")
    staff = authenticated_client(w.staff)
    base = f"/api/v1/admin/makerspaces/{w.space.pk}/machine-sessions"
    assert _ids(staff.get(f"{base}?machine={w.machines[1].pk}")) == {second.pk}
    assert _ids(staff.get(f"{base}?member={w.member.pk}")) == {first.pk}
    assert _ids(staff.get(f"{base}?source=device")) == {second.pk}
    assert staff.get(f"{base}?since=not-a-date").status_code == 400
