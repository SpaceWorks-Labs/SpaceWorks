"""Historical recovery stays readable with kiosk off and resolution appends one review."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.hardware_requests.models import ReplayCommand
from tests.makerspaces.station_support_cx11b_g4 import station_world
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.operations.route_support_cx11b_g4 import cycle, outsider, send, snapshot

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["hardware_requests:admin-kiosk-replay-list", "hardware_requests:admin-kiosk-replay-detail", "hardware_requests:admin-kiosk-replay-resolve"])
def test_recovery_routes_preserve_the_failed_attempt_and_review_while_kiosk_is_off(native, name, settings):
    w = station_world(native, settings)
    now = timezone.now()
    row = ReplayCommand.objects.create(makerspace=w.space, station=w.station, actor=w.user,
        operator_lease_id=w.lease.pk, station_session_id=w.lease.station_session_id,
        station_version=w.lease.station_version, client_command_id=uuid4(), aggregate_id=uuid4(),
        payload_fingerprint="f" * 64, operation_kind="assign_box", operation_version=1, sequence=1,
        client_created_at=now, expires_at=now + timedelta(minutes=10), state="failed", completed_at=now,
        failure_code="box_mismatch", failure_detail="Retained failure", subject_request=w.request)
    kwargs = {"makerspace_id": w.space.pk} if name.endswith("list") else {"pk": row.pk}
    url = reverse(name, kwargs=kwargs)
    method = "POST" if name.endswith("resolve") else "GET"
    body = {"resolution_code": "acknowledged_no_change"} if method == "POST" else {}
    foreign = outsider(native)
    before = snapshot()
    original = switch(w.space, "inventory.kiosk")

    def check(response):
        row.refresh_from_db()
        assert (row.state, row.failure_code, row.subject_request_id) == ("failed", "box_mismatch", w.request.pk)
        if method == "POST":
            assert (row.resolution_code, row.resolved_by_id) == ("acknowledged_no_change", w.user.pk)
            assert row.resolved_at is not None
        elif name.endswith("list"):
            assert [str(x["id"]) for x in response.data["results"]] == [str(row.pk)]
        else:
            assert str(response.data["id"]) == str(row.pk)
    # Historical recovery is explicitly independent of inventory.kiosk. List outsiders
    # see an empty scoped collection; addressed objects remain 404 (481/494/520).
    def probe():
        response = send(foreign, method, url, body)
        if name.endswith("list") and not native:
            assert response.data["results"] == []
        return response
    pair = (200, None) if name.endswith("list") else (404, "not_found")
    assert snapshot() == before
    cycle(w.space, None, lambda: send(w.client, method, url, body), check,
          foreign=probe, foreign_pair=pair, foreign_native=native, audit=("kiosk.replay_resolved",) if method == "POST" else ())
    switch(w.space, "inventory.kiosk", original=original)
    with no_domain_writes():
        replayed = send(w.client, method, url, body)
    assert response_pair(replayed) == (200, None)
    check(replayed)
