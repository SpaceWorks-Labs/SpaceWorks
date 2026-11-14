"""Secret-authenticated cron executes the real reminder worker, preserving pending loan rows."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tests.modules.switch_matrix_object_helpers import object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch
from tests.operations.route_support_cx11b_g4 import snapshot
from tests.test_return_reminders import make_product, make_request

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending]


@pytest.mark.parametrize("key", ["request_workflow", "loans.enabled"])
def test_return_reminder_cron_preserves_due_loan_off_and_queues_it_after_restore(key, settings, monkeypatch):
    settings.CRON_SECRET = "g4-private-cron-secret"
    space, _, _ = object_world(False)
    now = timezone.now()
    product = make_product(space)
    row = make_request(space, product, status="issued", contact_email="g4-reminder@example.test", due_at=now - timedelta(minutes=5))
    monkeypatch.setattr("apps.hardware_requests.services_return_reminders.timezone.now", lambda: now)
    client, url = APIClient(), reverse("hardware_requests:cron-return-reminders")
    before = snapshot()
    # Cron's secret is its standing contract; 481/494 staff normalization is irrelevant.
    with no_domain_writes():
        refused = client.post(url, {}, format="json", HTTP_X_CRON_SECRET="wrong")
    assert response_pair(refused) == (403, None)
    assert snapshot() == before
    with rolled_back():
        initial = client.post(url, {}, format="json", HTTP_X_CRON_SECRET=settings.CRON_SECRET)
        assert response_pair(initial) == (200, None)
        assert initial.data == {"sent": 1, "skipped": 0}
        row.refresh_from_db()
        assert row.return_reminder_sent_at == now
    assert snapshot() == before
    original = switch(space, key)
    with no_domain_writes():
        wrong_off = client.post(url, {}, format="json", HTTP_X_CRON_SECRET="wrong")
    assert response_pair(wrong_off) == (403, None)
    with no_domain_writes():
        off = client.post(url, {}, format="json", HTTP_X_CRON_SECRET=settings.CRON_SECRET)
    assert response_pair(off) == (200, None)
    assert off.data == {"sent": 0, "skipped": 0}
    assert snapshot() == before
    switch(space, key, original=original)
    with no_domain_writes():
        wrong_restored = client.post(url, {}, format="json", HTTP_X_CRON_SECRET="wrong")
    assert response_pair(wrong_restored) == (403, None)
    assert snapshot() == before
    response = client.post(url, {}, format="json", HTTP_X_CRON_SECRET=settings.CRON_SECRET)
    assert response_pair(response) == (200, None)
    assert response.data == {"sent": 1, "skipped": 0}
    row.refresh_from_db()
    assert row.return_reminder_sent_at == now
    product.refresh_from_db()
    assert (product.available_quantity, product.issued_quantity) == (0, 1)
    written = snapshot()
    again = client.post(url, {}, format="json", HTTP_X_CRON_SECRET=settings.CRON_SECRET)
    assert response_pair(again) == (200, None)
    assert again.data == {"sent": 0, "skipped": 0}
    assert snapshot() == written
    switch(space, key)
    assert snapshot() == written
    switch(space, key, original=original)
    assert snapshot() == written
