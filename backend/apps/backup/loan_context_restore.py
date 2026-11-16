"""Rotation of restored concurrency tokens under host-controlled recovery."""
from django.db import transaction
from apps.backup.models import RestoreOperation, DeploymentRecoveryState
from apps.makerspaces.loan_context_generations import rotate
from apps.makerspaces.models import Makerspace


@transaction.atomic
def rotate_after_restore(restore_id):
    # A host restore operation must exist in the restored database; missing or old
    # schema refuses, and the supervisor must keep writers stopped.
    operation = RestoreOperation.objects.select_for_update().get(pk=restore_id)
    state = DeploymentRecoveryState.objects.select_for_update().get(pk=1)
    if state.mode != DeploymentRecoveryState.Mode.QUIESCED or state.active_restore_id != operation.pk:
        raise RuntimeError("Context rotation requires the active quiesced restore.")
    from apps.data_export.loan_context_integrity import validate_loan_context_import
    for space in Makerspace.objects.select_for_update().order_by("pk").iterator():
        validate_loan_context_import(space.pk)
        rotate(space)
