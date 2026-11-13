"""Portable archives carry deletion fences before any global CSV exists."""

import json

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from tests.data_export.portable_helpers import archive_files, make_job, make_space, make_user
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


def test_portable_archive_with_deleted_identity_writes_lifecycle_sidecar():
    actor = make_user("lifecycle-exporter")
    deleted = make_user("lifecycle-deleted")
    now = timezone.now()
    User.objects.filter(pk=deleted.pk).update(is_active=False, deletion_requested_at=now)
    space = make_space("lifecycle-export")
    with enabled_encryption():
        HardwareRequest.objects.create(makerspace=space, requester=deleted,
                                       requester_username=deleted.username, status="returned")

        files, _raw, _manifest = archive_files(make_job(space, actor))

    lifecycle = json.loads(files["global/user_lifecycle.json"])
    assert lifecycle == {str(deleted.pk): {
        "deletion_requested_at": now.isoformat(), "deletion_purge_after": "",
        "purge_started_at": "", "account_purged_at": "",
    }}
    assert "global/users.csv" in files


def test_active_identities_do_not_create_a_lifecycle_sidecar(tmp_path):
    from apps.data_export.user_lifecycle import write_user_lifecycle
    write_user_lifecycle(tmp_path, [make_user("lifecycle-active")])
    assert not (tmp_path / "global").exists()
