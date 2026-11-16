"""Quarantine recovery must pass both the account surface and recovery-principal gate."""
import pytest
from django.urls import reverse

from apps.backup.models import DeploymentRecoveryState
from apps.backup.recovery import RESIDUAL_RISK, enter_quarantine, set_recovery_principal
from tests.backup.test_recovery import recovery_fixture
from .helpers import bearer_client

pytestmark = pytest.mark.django_db


def test_recovery_principal_can_read_and_acknowledge_through_real_jwt():
    root, _, restore = recovery_fixture()
    enter_quarantine(restore, "Stage 4 recovery")
    recovered = set_recovery_principal(root, "Recovery password 986!")
    api = bearer_client(recovered)
    path = reverse("backup-recovery-state")
    response = api.get(path)
    assert response.status_code == 200, response.data
    assert api.post(path, {"acknowledgement": "wrong"}, format="json").status_code == 400
    response = api.post(path, {"acknowledgement": RESIDUAL_RISK}, format="json")
    assert response.status_code == 200, response.data
    assert DeploymentRecoveryState.load().mode == "normal"


def test_another_platform_account_cannot_acknowledge_quarantine():
    from apps.accounts.models import User
    root, _, restore = recovery_fixture()
    enter_quarantine(restore, "Stage 4 recovery")
    set_recovery_principal(root, "Recovery password 986!")
    other = User.objects.create_superuser("s4-other-root", password="Other password 654!")
    api = bearer_client(other)
    path = reverse("backup-recovery-state")
    assert api.get(path).status_code == 401
    assert api.post(path, {"acknowledgement": RESIDUAL_RISK}, format="json").status_code == 401
    assert DeploymentRecoveryState.load().mode == "quarantined"
