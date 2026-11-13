"""#190 follow-up: a space's keys and capability purge from the web console. Local only."""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.encryption.models import KeyRotationJob
from apps.procurement.models import ToBuyItem
from tests.encryption.conftest import enabled_encryption
from tests.r2_superadmin_local.helpers import api, manager, space, superadmin

pytestmark = pytest.mark.django_db


def base(lab):
    return f"/api/v1/admin/platform/spaces/{lab.pk}/"


@pytest.fixture
def world():
    cache.clear()
    lab = space("keys-lab")
    return SimpleNamespace(root=superadmin("keys-root"), lab=lab, boss=manager(lab))


def test_staff_and_stale_sessions_never_reach_space_keys(world):
    assert api(world.boss).get(base(world.lab) + "keys").status_code in {401, 403}
    assert api(world.boss).get(base(world.lab) + "capability-purge").status_code in {401, 403}
    stale = APIClient(HTTP_HOST="localhost")
    stale.force_authenticate(user=world.root)
    response = stale.post(base(world.lab) + "keys/rotate", {"action": "rotate_publishable_key",
                                                            "confirm_slug": world.lab.slug}, format="json")
    assert response.status_code == 403


def test_browser_key_rotation_needs_the_slug_and_audits_in_the_space(world):
    client = api(world.root)
    old = world.lab.public_api_key
    wrong = client.post(base(world.lab) + "keys/rotate", {"action": "rotate_publishable_key", "confirm_slug": "nope"}, format="json")
    assert wrong.status_code == 400 and wrong.json()["code"] == "confirm_slug_mismatch"
    ok = client.post(base(world.lab) + "keys/rotate", {"action": "rotate_publishable_key", "confirm_slug": world.lab.slug},
                     format="json")
    assert ok.status_code == 202 and ok.json()["publishable_key_rotated_at"]
    world.lab.refresh_from_db()
    assert world.lab.public_api_key != old and old not in ok.content.decode()
    assert AuditLog.objects.filter(action="makerspace.public_api_key_rotated", makerspace=world.lab).exists()


def test_data_key_rotation_starts_a_background_job_with_progress(world):
    with enabled_encryption():
        from tests.encryption.test_key_rotation import _space_with_requests
        world.lab, _rows = _space_with_requests(1)  # an encrypted write gives the space its first key
        client = api(world.root)
        with mock.patch("apps.encryption.rekey_tasks.advance_key_jobs_task.delay"):
            response = client.post(base(world.lab) + "keys/rotate", {"action": "rotate_dek", "confirm_slug": world.lab.slug},
                                   format="json")
        assert response.status_code == 202, response.json()
        assert response.json()["running"]["kind"] == "rotation"
        busy = client.post(base(world.lab) + "keys/rotate", {"action": "emergency_rekey", "confirm_slug": world.lab.slug},
                           format="json")
        assert busy.status_code == 409 and busy.json()["code"] == "key_action_refused"
        assert KeyRotationJob.objects.filter(makerspace=world.lab).count() == 1
        assert AuditLog.objects.filter(action="encryption.key_rotated", makerspace=world.lab).exists()


def test_archive_jobs_are_queued_only_for_this_spaces_stale_archives(world):
    client = api(world.root)
    refused = client.post(base(world.lab) + "keys/archives/00000000-0000-0000-0000-000000000001",
                          {"action": "purge", "confirm_slug": world.lab.slug}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "archive_not_stale"
    archive = SimpleNamespace(pk="11111111-1111-1111-1111-111111111111", scope="makerspace", makerspace_id=world.lab.pk)
    with mock.patch("apps.backup.platform_key_rotation.stale_archives", return_value=[archive]), \
            mock.patch("apps.backup.archive_reencrypt.can_reencrypt", return_value=False), \
            mock.patch("apps.audit.services.record") as record, \
            mock.patch("apps.backup.tasks_space_keys.space_archive_key_task.delay") as delay:
        not_openable = client.post(base(world.lab) + f"keys/archives/{archive.pk}",
                                   {"action": "reencrypt", "confirm_slug": world.lab.slug}, format="json")
        assert not_openable.status_code == 409 and not_openable.json()["code"] == "not_reencryptable"
        queued = client.post(base(world.lab) + f"keys/archives/{archive.pk}", {"action": "purge", "confirm_slug": world.lab.slug},
                             format="json")
        assert queued.status_code == 202 and queued.json()["job"]["state"] == "queued"
        again = client.post(base(world.lab) + f"keys/archives/{archive.pk}", {"action": "purge", "confirm_slug": world.lab.slug},
                            format="json")
        assert again.status_code == 409 and again.json()["code"] == "archive_job_running"
    assert any(call.args[1] == "backup.archive_key_job_queued" for call in record.call_args_list)
    assert delay.call_count <= 1


def test_the_archive_job_records_its_outcome(world):
    from apps.backup import space_archive_keys
    from apps.backup.platform_key_rotation import KeyRotationError
    row = SimpleNamespace(pk="22222222-2222-2222-2222-222222222222")
    with mock.patch("apps.backup.models.BackupArchive.objects") as objects, \
            mock.patch("apps.backup.archive_reencrypt.purge_archive", side_effect=KeyRotationError("purge_failed", "x")):
        objects.filter.return_value.first.return_value = row
        assert space_archive_keys.run(row.pk, "purge", world.root.pk) == "failed"
    assert space_archive_keys.job_state(row.pk)["error_code"] == "purge_failed"


def test_capability_purge_previews_needs_the_key_typed_and_the_switch_off(world):
    ToBuyItem.objects.create(makerspace=world.lab, kind="printing", name="PLA")
    world.lab.enabled_features = [*(world.lab.enabled_features or []), "machines.tobuy"]
    world.lab.save(update_fields=["enabled_features"])
    client = api(world.root)
    plans = {plan["key"]: plan for plan in client.get(base(world.lab) + "capability-purge").json()}
    assert plans["machines.tobuy"]["counts"]["to_buy_items"] == 1 and plans["machines.tobuy"]["switched_on"]
    url = base(world.lab) + "capability-purge"
    assert client.post(url, {"key": "machines.tobuy", "confirm": "machines"}, format="json").json()["code"] == "confirm_mismatch"
    on = client.post(url, {"key": "machines.tobuy", "confirm": "machines.tobuy"}, format="json")
    assert on.status_code == 409 and on.json()["code"] == "purge_refused"
    world.lab.enabled_features = [key for key in world.lab.enabled_features if key != "machines.tobuy"]
    world.lab.save(update_fields=["enabled_features"])
    done = client.post(url, {"key": "machines.tobuy", "confirm": "machines.tobuy"}, format="json")
    assert done.status_code == 200 and done.json()["counts"] == {"to_buy_items": 1}
    assert not ToBuyItem.objects.filter(makerspace=world.lab).exists()
    assert AuditLog.objects.filter(action="makerspace.capability_purged", makerspace=world.lab, actor=world.root).exists()
