"""Keep external rotation I/O on the retained scope-lock connection."""
from functools import wraps


def rotation_scope(callback):
    @wraps(callback)
    def guarded(rotation, sink, *args, **kwargs):
        from .batches import scope_session_lock
        from apps.backup.managed.audit_guard import guarded_anchor_sink
        with scope_session_lock(rotation.makerspace_id) as guard:
            result = callback(rotation, guarded_anchor_sink(sink), *args, **kwargs)
            guard.assert_valid()
            return result
    return guarded
