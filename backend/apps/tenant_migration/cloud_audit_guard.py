"""Publication and external anchor proof share one retained Django session."""
from functools import wraps


def capture_scope(callback):
    @wraps(callback)
    def guarded(capture_id, *args, **kwargs):
        from apps.audit.batches import scope_session_lock
        from .models import TenantDumpCapture
        space = TenantDumpCapture.objects.values_list("makerspace_id", flat=True).get(pk=capture_id)
        with scope_session_lock(space) as guard:
            result = callback(capture_id, *args, **kwargs)
            guard.assert_valid()
            return result
    return guarded
