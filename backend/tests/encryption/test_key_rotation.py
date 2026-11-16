"""Lane L8 per-space key rotation (#120): new version for writes now, background re-encrypt, retire."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.encryption.models import KeyRotationJob, MakerspaceEncryptionKey, RetiredPublishableKey
from apps.encryption.publishable_keys import makerspace_id_for_retired_key, rotate_publishable_key
from apps.encryption.rekey_tasks import advance_running
from apps.encryption.rotation import start_dek_rotation
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db


def _space_with_requests(count=3):
    token = uuid.uuid4().hex[:8]
    space = Makerspace.objects.create(name=f"Rotate {token}", slug=f"rotate-{token}")
    user = get_user_model().objects.create_user(username=f"rotate-{token}")
    rows = [HardwareRequest.objects.create(
        makerspace=space, requester=user, requester_username=user.username,
        requester_name=f"Ada {index}", requester_contact_email=f"{token}{index}@example.test",
    ) for index in range(count)]
    return space, rows


def _versions(row):
    with connection.cursor() as cursor:
        cursor.execute("SELECT requester_name, requester_contact_email FROM hardware_requests_hardwarerequest "
                       "WHERE id = %s", [row.pk])
        return {int(value.split(":")[3]) for value in cursor.fetchone() if value}


def _superadmin():
    return get_user_model().objects.create_superuser(username=f"root-{uuid.uuid4().hex[:6]}", password="x")


def _run_to_completion():
    for _ in range(20):
        if not advance_running():
            return
    raise AssertionError("key job did not finish")


def test_rotation_switches_writes_reencrypts_rows_and_retires_the_old_version():
    with enabled_encryption():
        space, rows = _space_with_requests()
        assert _versions(rows[0]) == {1}
        actor = _superadmin()
        job = start_dek_rotation(actor, space)
        assert (job.from_version, job.to_version, job.kind) == (1, 2, "rotation")
        fresh = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username="fresh",
                                               requester_name="New write")
        assert _versions(fresh) == {2}  # the new version is the write key at once
        assert _versions(rows[1]) == {1}  # existing rows wait for the background job
        _run_to_completion()
        job.refresh_from_db()
        assert job.status == "completed" and job.rows_done >= len(rows)
        assert all(_versions(row) == {2} for row in rows)
        assert HardwareRequest.objects.get(pk=rows[0].pk).requester_name == "Ada 0"
        assert MakerspaceEncryptionKey.objects.get(makerspace=space, version=1).status == "disabled"
        actions = set(AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))
        assert {"encryption.key_rotated", "encryption.key_rotation_completed", "encryption.dek_disabled"} <= actions


def test_one_running_job_per_space_and_chunks_are_idempotent():
    with enabled_encryption():
        space, rows = _space_with_requests(5)
        actor = _superadmin()
        job = start_dek_rotation(actor, space)
        with pytest.raises(ValidationError):
            start_dek_rotation(actor, space)
        assert advance_running(budget=2) == 1
        job.refresh_from_db()
        done = job.rows_done
        assert 0 < done <= 2 and job.status == "running"
        _run_to_completion()
        job.refresh_from_db()
        assert job.status == "completed" and job.rows_done == len(rows)


def test_a_version_still_referenced_is_retained_not_disabled(monkeypatch):
    with enabled_encryption():
        space, _rows = _space_with_requests(1)
        job = start_dek_rotation(_superadmin(), space)
        from apps.encryption import rekey_finish
        monkeypatch.setattr(rekey_finish, "version_referenced", lambda makerspace_id, version: True)
        _run_to_completion()
        job.refresh_from_db()
        assert job.retained_versions == [1]
        assert MakerspaceEncryptionKey.objects.get(makerspace=space, version=1).status == "rotated"


def test_rotation_without_a_key_is_refused():
    space = Makerspace.objects.create(name="No key", slug=f"no-key-{uuid.uuid4().hex[:6]}")
    with pytest.raises(ValidationError):
        start_dek_rotation(_superadmin(), space)


def test_publishable_key_rotation_keeps_the_old_key_for_the_grace_window(settings):
    settings.PUBLISHABLE_KEY_ROTATION_GRACE_HOURS = 72
    space = Makerspace.objects.create(name="Pub", slug=f"pub-{uuid.uuid4().hex[:6]}")
    old = space.public_api_key
    new, valid_until = rotate_publishable_key(_superadmin(), space)
    space.refresh_from_db()
    assert space.public_api_key == new != old
    assert makerspace_id_for_retired_key(old) == space.pk
    assert makerspace_id_for_retired_key(old, now=valid_until + timedelta(seconds=1)) is None
    row = AuditLog.objects.get(action="makerspace.public_api_key_rotated", makerspace=space)
    assert old not in str(row.meta) and new not in str(row.meta)
    assert RetiredPublishableKey.objects.filter(makerspace=space, key=old).exists()


def test_key_events_are_visible_to_managers_only():
    from rest_framework.test import APIClient
    client = APIClient()
    with enabled_encryption():
        space, _rows = _space_with_requests(1)
        root = _superadmin()
        job = start_dek_rotation(root, space)
        url = reverse("admin-makerspace-key-events", kwargs={"makerspace_id": space.pk})
        client.force_authenticate(root)
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["results"][0]["id"] == job.pk
        assert "wrapped_dek" not in response.content.decode()
        stranger = get_user_model().objects.create_user(username=f"stranger-{uuid.uuid4().hex[:6]}")
        client.force_authenticate(stranger)
        assert client.get(url).status_code in {403, 404}


def _control_client():
    from django.test import Client
    from apps.accounts.models import User
    from tests.accounts.reauth_helpers import force_recent_control_login
    from tests.return_helpers import make_user
    root = make_user(f"control-keys-{uuid.uuid4().hex[:6]}", role=User.Role.SUPERADMIN,
                     access_status=User.AccessStatus.ACTIVE, is_staff=True, is_superuser=True)
    client = Client(HTTP_HOST="localhost")
    force_recent_control_login(client, root)
    return client


def test_control_keys_page_rotates_after_reauthentication():
    with enabled_encryption():
        space, _rows = _space_with_requests(1)
        client = _control_client()
        url = reverse("admin:makerspaces_makerspace_keys", args=[space.pk])
        assert client.get(url).status_code == 200
        response = client.post(url, {"action": "emergency_rekey"})
        assert response.status_code == 302
        job = KeyRotationJob.objects.get(makerspace=space)
        assert job.kind == "emergency_rekey" and job.to_version == 2
        assert AuditLog.objects.filter(makerspace=space, action="encryption.emergency_rekey_started").exists()


def test_control_rls_page_shows_the_mode(settings):
    response = _control_client().get(reverse("control-rls"))
    assert response.status_code == 200
    assert b"Row-level security" in response.content
    mode = response.context_data["state"]["mode"]
    if settings.TENANT_RLS_PROBE_ROLE and settings.TENANT_RLS_MODE == "auto":
        assert mode == "enforce"
    status_labels = {
        "enforce": b"<strong>Enforced.</strong>",
        "report": b"<strong>Report-only.</strong>",
        "inactive": b"<strong>Inactive.</strong>",
        "off": b"<strong>Off.</strong>",
    }
    assert status_labels[mode] in response.content


def test_publishable_middleware_accepts_a_retired_key_only_inside_its_window(settings, monkeypatch):
    from django.test import RequestFactory
    from apps.inventory.middleware_publishable import PublishableKeyMixin
    space = Makerspace.objects.create(name="Site", slug=f"site-{uuid.uuid4().hex[:6]}")
    Makerspace.objects.filter(pk=space.pk).update(public_site_enabled=True)
    old = space.public_api_key
    rotate_publishable_key(_superadmin(), space)
    checker = PublishableKeyMixin()
    seen = []
    monkeypatch.setattr(PublishableKeyMixin, "_makerspace_scope_ok", lambda self, request, ms: True, raising=False)
    monkeypatch.setattr(PublishableKeyMixin, "_publishable_origin_ok",
                        lambda self, request, ms: seen.append(ms.pk) or True)
    request = RequestFactory().get("/api/v1/public/x", HTTP_X_PUBLISHABLE_KEY=old)
    assert checker._publishable_key_is_valid(request) and seen == [space.pk]
    RetiredPublishableKey.objects.filter(key=old).update(valid_until=timezone.now() - timedelta(seconds=1))
    assert not checker._publishable_key_is_valid(RequestFactory().get("/x", HTTP_X_PUBLISHABLE_KEY=old))
