"""Decision 516: website PUT in production's autocommit shape, browser and native."""
import pytest
from django.db import connection

from apps.audit.models import AuditLog
from tests.modules.switch_matrix_object_contracts import OPERATIONS
from tests.modules.switch_matrix_object_helpers import (
    no_domain_writes, object_world, request, response_pair, retained,
)
from tests.modules.switch_matrix_helpers import dependents_closure

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_events]
WEBSITE = next(op for op in OPERATIONS if op.name == "admin-event-website-content" and op.method == "PUT")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["events", "events.website"])
def test_website_put_saves_refuses_off_and_restores_without_a_caller_transaction(native, key):
    from dataclasses import replace

    space, client, objects = object_world(native)
    page = objects["event_page"]
    assert connection.get_autocommit() is True
    assert connection.atomic_blocks == []
    response = request(client, WEBSITE, objects)
    assert response_pair(response) == (200, None), response.data
    assert response.data["revision"] == 2
    page.refresh_from_db()
    assert page.revision == 2
    assert list(AuditLog.objects.filter(makerspace=space, action="event.website_saved")
                .values_list("target_id", "meta")) == [(str(page.pk), {"revision": 2})]
    before, audits = retained(objects), AuditLog.objects.count()

    field = "enabled_features" if "." in key else "enabled_modules"
    original = list(getattr(space, field))
    removed = {key} if "." in key else {key} | dependents_closure(key)
    setattr(space, field, sorted(set(original) - removed))
    space.save(update_fields=[field])
    with no_domain_writes():
        response = request(client, WEBSITE, objects)
    code = "feature_disabled" if "." in key else "module_disabled"
    assert response_pair(response) == (404, code), response.data
    assert response.data["feature" if "." in key else "module"] == key
    assert retained(objects) == before
    assert AuditLog.objects.count() == audits

    setattr(space, field, original)
    space.save(update_fields=[field])
    restored = replace(WEBSITE, body=(("revision", 2), ("sections", []), ("sessions", [])))
    response = request(client, restored, objects)
    assert response_pair(response) == (200, None), response.data
    assert response.data["revision"] == 3
    page.refresh_from_db()
    assert page.revision == 3
    assert list(AuditLog.objects.filter(makerspace=space, action="event.website_saved").order_by("pk")
                .values_list("target_id", "meta")) == [
        (str(page.pk), {"revision": 2}), (str(page.pk), {"revision": 3}),
    ]
    before, audits = retained(objects), AuditLog.objects.count()

    # A stale valid integer reaches domain validation; a malformed one reaches DRF.
    response = request(client, WEBSITE, objects)
    assert (response.status_code, response.data["revision"].code) == (400, "invalid")
    assert response.json() == {"revision": "The page changed. Reload before saving."}
    assert retained(objects) == before
    assert AuditLog.objects.count() == audits
    malformed = replace(WEBSITE, body=(("revision", "invalid"), ("sections", []), ("sessions", [])))
    response = request(client, malformed, objects)
    assert (response.status_code, response.data["revision"][0].code) == (400, "invalid")
    assert response.json() == {"revision": ["A valid integer is required."]}
    assert retained(objects) == before
    assert AuditLog.objects.count() == audits
    assert connection.get_autocommit() is True
    assert connection.atomic_blocks == []
