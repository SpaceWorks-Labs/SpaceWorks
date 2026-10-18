"""Request-scoped marker for native device sessions (membership-only authority).

A per-object attribute on `request.user` is lost whenever a service reloads the actor
(for example `resource_grant_locks.lock_tenant_authority()` re-reads the User under a row
lock). The marker therefore lives in a context variable keyed by user id for the duration
of one request, set by `SpaceWorksJWTAuthentication` and reset by
`NativeSessionContextMiddleware`. Celery tasks and management commands never see it.
"""

from contextvars import ContextVar

_NATIVE_USER_ID: ContextVar[int | None] = ContextVar("native_session_user_id", default=None)


def mark_native_session(user):
    _NATIVE_USER_ID.set(getattr(user, "pk", None))


def is_native_session(actor):
    if actor is None:
        return False
    if getattr(actor, "native_device_session", False):
        return True
    marked = _NATIVE_USER_ID.get()
    return marked is not None and marked == getattr(actor, "pk", None)


class NativeSessionContextMiddleware:
    """Clear the marker after every request so a worker thread never carries it over."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _NATIVE_USER_ID.set(None)
        try:
            return self.get_response(request)
        finally:
            _NATIVE_USER_ID.reset(token)
