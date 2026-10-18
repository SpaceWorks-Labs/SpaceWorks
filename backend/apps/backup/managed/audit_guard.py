"""Fence each remote anchor call with the active retained database session."""

from functools import wraps

from config.cloud_database.session import current_session


class GuardedAnchorSink:
    def __init__(self, sink):
        self.sink = sink

    def __getattr__(self, name):
        value = getattr(self.sink, name)
        if not callable(value):
            return value

        @wraps(value)
        def checked(*args, **kwargs):
            guard = current_session()
            if guard is not None:
                guard.assert_valid()
            result = value(*args, **kwargs)
            if guard is not None:
                guard.assert_valid()
            return result

        return checked


def guarded_anchor_sink(sink):
    return sink if isinstance(sink, GuardedAnchorSink) else GuardedAnchorSink(sink)
