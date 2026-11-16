"""Restore admission generation rotations; no runtime proof until executed."""
import pytest
from apps.backup.loan_context_restore import rotate_after_restore
from apps.backup.models import DeploymentRecoveryState
from apps.backup.restore_services import enter_quiescence
from apps.makerspaces.models import Makerspace
from tests.backup.test_restore_services import restore_fixture

pytestmark = pytest.mark.django_db(transaction=True)


def test_restore_rotation_requires_active_quiesced_operation_and_changes_both():
    actor, operation = restore_fixture()
    space = Makerspace.objects.create(name="Restore epoch", slug="restore-epoch")
    before = dict(space.loan_context_generations)
    DeploymentRecoveryState.load()
    with pytest.raises(RuntimeError, match="quiesced"):
        rotate_after_restore(operation.pk)
    space.refresh_from_db()
    assert space.loan_context_generations == before
    enter_quiescence(operation.pk)
    rotate_after_restore(operation.pk)
    space.refresh_from_db()
    assert space.loan_context_generations["events"] != before["events"]
    assert space.loan_context_generations["bookings"] != before["bookings"]
    assert DeploymentRecoveryState.load().mode == DeploymentRecoveryState.Mode.QUIESCED
