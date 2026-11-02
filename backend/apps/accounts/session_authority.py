"""Request-scoped staff-authority limit for sessions that never carry full staff authority.

One account per person: a person's staff roles are staff-TRACK rows, and RBAC reads them
for every request the person makes. Two kinds of session must not see them (#162(2)):

- a native MEMBER device grant (a phone signed in as a member) carries no staff
  authority, and a native STAFF grant carries only its one fixed tenant's;
- a claim session (a bounded walk-in session) never carries staff authority.

The route gate in ``surface_policy`` already refuses staff routes for both, but a
MEMBER route that calls ``rbac.can`` must not find staff actions either. Authentication
sets the limit here, keyed by user id (a re-read actor keeps it, like ``native_session``);
``rbac_memberships._staff_rows`` applies it. ``NativeSessionContextMiddleware`` clears it
after every request; Celery tasks and management commands never see one.
"""

from contextvars import ContextVar

_LIMIT: ContextVar[tuple[int, frozenset] | None] = ContextVar("staff_authority_limit", default=None)


def limit_staff_authority(user, makerspace_ids=()):
    """Allow staff-track authority for ``user`` only in ``makerspace_ids`` (none by default)."""
    _LIMIT.set((getattr(user, "pk", None), frozenset(int(pk) for pk in makerspace_ids)))


def staff_authority_limit(actor):
    """The makerspace ids this request may exercise staff authority in, or ``None`` (no limit)."""
    marked = _LIMIT.get()
    if marked is None or actor is None or marked[0] != getattr(actor, "pk", None):
        return None
    return marked[1]


def reset():
    """Return a token that restores the previous value (used by the request middleware)."""
    return _LIMIT.set(None)


def restore(token):
    _LIMIT.reset(token)
