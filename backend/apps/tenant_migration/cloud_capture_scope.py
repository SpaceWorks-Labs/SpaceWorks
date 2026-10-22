"""Lane D managed capture shares archive exclusion and the complete writer drain."""
from contextlib import contextmanager, nullcontext
from django.conf import settings


@contextmanager
def capture_scope(capture_id, modes):
    if settings.SPACEWORKS_DEPLOYMENT_MODE != "managed":
        yield
        return
    from apps.backup.operation_lock import deployment_operation_lock
    from apps.backup.cloud_continuity import operation_guard, current_operation
    from apps.backup.managed.capture import capture_pause
    lock = nullcontext(current_operation()) if current_operation() else deployment_operation_lock()
    with lock as guard, operation_guard(guard):
        pause = capture_pause(capture_id) if "quiesced" in modes.values() else nullcontext()
        with pause:
            yield
