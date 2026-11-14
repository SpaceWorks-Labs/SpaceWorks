"""Camera convenience and generic command routes share the snapshot allowance."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.devices.models import AdapterCommand
from tests.devices.test_adapter_watch_aim_credential_mod2b import watching
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts

pytestmark = [pytest.mark.django_db, pytest.mark.area_devices, pytest.mark.area_machines]


def scenario(route, surface, settings, monkeypatch):
    case = watching("cx7-snapshot-quota")
    space = case["space"]
    space.resource_limit_overrides = {"adapter_snapshots": 1}
    space.save(update_fields=["resource_limit_overrides"])
    pair = callers(space, surface, settings, monkeypatch)
    if route == "generic":
        url = reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]])
        body = {"capability": "media.snapshot", "command": "snapshot", "params": {"watch_id": str(case["watch"])}}
    else:
        url = reverse("devices:admin-adapter-watch-snapshot", args=[case["watch"]])
        body = {}
    return case, pair, url, body


@pytest.mark.parametrize("route", ["generic", "watch"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_snapshot_creator_max_then_next_refuses_without_command_or_audit(route, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    case, pair, url, body = scenario(route, surface, settings, monkeypatch)
    assert pair[0].post(url, body, format="json").status_code == 201
    before = list(AdapterCommand.objects.order_by("pk").values())
    audits = list(AuditLog.objects.order_by("pk").values())
    refused = pair[0].post(url, body, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == "adapter_snapshots_quota_reached"
    assert list(AdapterCommand.objects.order_by("pk").values()) == before
    assert list(AuditLog.objects.order_by("pk").values()) == audits
    assert AdapterCommand.objects.filter(makerspace=case["space"], command="snapshot").count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("route", ["generic", "watch"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_snapshot_creators_at_last_slot_admit_one(route, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    case, pair, url, body = scenario(route, surface, settings, monkeypatch)
    results = race_posts(pair, url, [body, body])
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == ["adapter_snapshots_quota_reached"]
    assert AdapterCommand.objects.filter(makerspace=case["space"], command="snapshot").count() == 1
    assert AuditLog.objects.filter(makerspace=case["space"], action="devices.adapter_command_queued").count() == 1
