"""The ordinary archive consumer refuses before creating recovery state."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.backup.models import BackupArchive, DeploymentRecoveryState, RestoreOperation
from apps.backup.restore_services import request_restore
from tests.return_helpers import make_space, make_user
from apps.accounts.models import User


@pytest.mark.django_db
def test_ordinary_tenant_archive_is_not_a_deployment_or_portable_restore():
    actor = make_user("verify-recovery-admin", role=User.Role.SUPERADMIN)
    space = make_space("verify-custody-only")
    archive = BackupArchive.objects.create(
        scope="makerspace", makerspace=space, requested_by=actor,
        manifest={"format": "spaceworks-phase5a-v3"}, status="available",
        expires_at=timezone.now() + timedelta(days=1),
    )
    before = list(DeploymentRecoveryState.objects.values())
    count = RestoreOperation.objects.count()
    with pytest.raises(ValidationError, match="Only full-deployment"):
        request_restore(actor, archive, "deployment")
    assert RestoreOperation.objects.count() == count
    assert list(DeploymentRecoveryState.objects.values()) == before
    archive.refresh_from_db()
    assert archive.status == "available"
