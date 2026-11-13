"""The superadmin may write in a paused or read-only space (#195, applying #110/#190).

Everyone else stays refused by ``write_policy``. A bypass lives for one HTTP request or
one Celery job and has three phases:

* ``pending`` -- the gate middleware saw a valid platform-superadmin bearer token (or a
  ``/control/`` request, which only superusers reach). Before authentication there is no
  user yet, so a pending bypass admits ONLY the middleware's own boundary check.
* ``confirmed`` -- the authenticated late guard (``assert_request_write_allowed``), the
  ``/control/`` admin gate, or a job published from a confirmed request proved the actor
  is a live platform superadmin. Every write it admits in a restricted space is audited
  once per space as ``space_control.superadmin_bypass`` with ``bypass_space_control``.
* anything else (no bypass, a revoked one, a pending one after dispatch) -- refused.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from apps.accounts.platform_authority import is_platform_superadmin

HEADER = "space_control_bypass_actor"
_state = ContextVar("space_controls_superadmin_bypass", default=None)


@dataclass
class Bypass:
    label: str
    actor: object = None
    phase: str = "pending"  # pending | dispatched | confirmed | control | revoked
    audited: set = field(default_factory=set)


@contextmanager
def scope(bypass):
    """Open ``bypass`` for the block; ``None`` leaves any outer bypass as it is."""
    if bypass is None:
        yield None
        return
    token = _state.set(bypass)
    try:
        yield bypass
    finally:
        _state.reset(token)


def bearer_superadmin(request):
    """The live platform superadmin a request's bearer token names, else None (a hint only)."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return None
    try:
        from apps.accounts.models import User
        from apps.accounts.tokens import SpaceWorksAccessToken

        token = SpaceWorksAccessToken(header.removeprefix("Bearer ").strip())
        if token.get("kind") != "platform":
            return None
        user = User.objects.filter(pk=token.get("user_id")).first()
    except Exception:
        return None
    return user if is_platform_superadmin(user) else None


def for_request(request, view_name):
    """The bypass the gate middleware opens for one unsafe request, or None."""
    if request.path_info.startswith("/control/"):
        return Bypass(label="control", phase="control")
    if bearer_superadmin(request) is not None:
        return Bypass(label=view_name or request.path_info[:200])
    return None


def mark_dispatched():
    """Called by the middleware once its boundaries are held: pending stops admitting."""
    bypass = _state.get()
    if bypass is not None and bypass.phase == "pending":
        bypass.phase = "dispatched"


def confirm(user):
    """Late, authenticated confirmation; any other actor loses the bypass."""
    bypass = _state.get()
    if bypass is None or bypass.phase == "revoked":
        return
    if is_platform_superadmin(user):
        bypass.actor = user
        if bypass.phase != "control":
            bypass.phase = "confirmed"
    elif bypass.phase != "control":
        bypass.phase = "revoked"


def allows(makerspace_id, restricted):
    """Whether the current actor may write despite ``restricted``; audits confirmed writes."""
    bypass = _state.get()
    if bypass is None or bypass.phase in ("revoked", "dispatched"):
        return False
    if bypass.actor is not None and makerspace_id not in bypass.audited:
        bypass.audited.add(makerspace_id)
        from apps.audit import services as audit
        from apps.makerspaces.models import Makerspace

        space = Makerspace.objects.filter(pk=makerspace_id).first()
        audit.record(bypass.actor, "space_control.superadmin_bypass", makerspace=space, target=space,
                     meta={"bypass_space_control": restricted, "path": bypass.label[:200]})
    return True


def publish_headers(headers=None, **_kwargs):
    """Celery ``before_task_publish``: a job queued by a confirmed superadmin carries it."""
    bypass = _state.get()
    if headers is not None and bypass is not None and bypass.phase == "confirmed" and bypass.actor is not None:
        headers[HEADER] = bypass.actor.pk


def for_task(task_request, task_name):
    """The confirmed bypass a job inherits from the superadmin action that queued it."""
    actor_id = getattr(task_request, HEADER, None) or (getattr(task_request, "headers", None) or {}).get(HEADER)
    if not actor_id:
        return None
    from apps.accounts.models import User

    user = User.objects.filter(pk=actor_id).first()
    if not is_platform_superadmin(user):
        return None
    return Bypass(label=f"task:{task_name}"[:200], actor=user, phase="confirmed")
