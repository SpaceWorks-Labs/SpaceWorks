"""537: a switch disabled during storage I/O never becomes a persisted replay failure."""
from contextlib import ExitStack

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.hardware_requests.models import ReplayCommand
from tests.hardware_requests.replay_helpers import envelope
from tests.makerspaces.station_support_cx11b_g4 import station_world
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import switch
from tests.payments.switch_helpers_cx11b_p2 import no_policy_writes as no_domain_writes
from tests.operations.route_support_cx11b_g4 import snapshot

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_devices]


@pytest.mark.parametrize("key", ["inventory.kiosk", "request_workflow", "loans.enabled"])
def test_switch_disabled_after_storage_keeps_claim_without_failure_writes(key, settings, monkeypatch):
    w = station_world(False, settings)
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload",
        lambda key, mime, *, max_bytes, exact_bytes=None: {"url": "https://storage.example.test/upload",
            "fields": {"key": f"staging/{key}", "Content-Type": mime}})
    data = envelope(w, "reviewed_issue", payload={"request_id": w.request.pk})
    kwargs = {"public_token": w.credential.public_token}
    prepared = w.client.post(reverse("kiosk-replay-prepare", kwargs=kwargs), data, format="json", **w.headers)
    assert response_pair(prepared) == (200, None)
    assert prepared.data["state"] == "prepared"
    kwargs["client_command_id"] = data["client_command_id"]
    observed = {}
    with ExitStack() as fence:
        def finalize(photo, max_bytes):
            switch(w.space, key)
            observed["rows"] = snapshot()
            fence.enter_context(no_domain_writes())
            return photo
        monkeypatch.setattr("apps.evidence.storage.finalize_upload", finalize)
        response = w.client.post(reverse("kiosk-replay-execute", kwargs=kwargs), data, format="json", **w.headers)
    assert response_pair(response) == (404, "feature_disabled" if key == "inventory.kiosk" else "module_disabled")
    assert snapshot() == observed["rows"]
    row = ReplayCommand.objects.get(pk=prepared.data["replay_id"])
    assert (row.state, row.claim_attempts, row.failure_code, row.completed_at) == ("claimed", 1, None, None)
    assert row.claim_token is not None and row.claimed_at is not None
    assert not AuditLog.objects.filter(action="kiosk.replay_failed", meta__replay_id=str(row.pk)).exists()
    w.request.refresh_from_db()
    w.product.refresh_from_db()
    assert w.request.status == "accepted"
    assert (w.product.available_quantity, w.product.reserved_quantity, w.product.issued_quantity) == (9, 1, 0)


def test_direct_fence_records_and_blocks_even_a_swallowed_write():
    from django.db import connection
    with pytest.raises(AssertionError, match="UPDATE cx11b_forbidden"):
        with no_domain_writes():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE cx11b_forbidden SET value = 1")
            except AssertionError:
                pass  # A fail-safe adapter must not hide the recorded attempt.
