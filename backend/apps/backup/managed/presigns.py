"""Record the actual maximum externally writable interval before signing."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone


def register_presign(seconds):
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed":
        return
    from .writers import _state, WriterFenceError
    from .models_staging import ManagedPresignLease
    from apps.operations.cloud_runtime import check
    check()
    if type(seconds) is not int or not 1 <= seconds <= 604800:
        raise WriterFenceError("Presign lifetime is outside the supported drain bound.")
    with transaction.atomic():
        state = _state()
        if state.paused_by is not None:
            from .capture import active_capture
            from apps.storage_clients import _qualifying
            # Only the retained owner may run fixed, private qualification
            # requests during a handoff. They never issue a browser credential;
            # unknown/failed probe requests leave the pause held.
            if seconds > 60 or not _qualifying.get() or not active_capture():
                raise WriterFenceError("Capture has closed presign issuance.")
        ManagedPresignLease.objects.create(
            generation=state.generation,
            expires_at=timezone.now() + timedelta(seconds=seconds + getattr(settings, "MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS", 0)),
        )
