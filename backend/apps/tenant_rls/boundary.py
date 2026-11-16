"""Where bindings come from: the request, task and per-tenant fan-out boundaries.

* Request: ``/control/`` and the routes in ``ROUTE_CAPABILITIES`` bind their capability;
  a route the origin-scope resolver maps to its makerspace(s) (the same authoritative
  URL/model ownership the source gate trusts) binds that tenant scope; anything else is
  open. Views keep scoping through ``rbac`` - RLS is the backstop, not the mechanism.
* Celery task: ``TASK_CAPABILITIES`` by task name, else a ``makerspace_id`` argument
  binds that tenant, else open. Bound in ``task_prerun``, released in ``task_postrun``.
* ``tenant_migration.gate_runtime.fanout_tenant_write``: each tenant of a scheduled sweep.
"""

import inspect
import logging

from .capabilities import PATH_CAPABILITIES, ROUTE_CAPABILITIES, TASK_CAPABILITIES, capability_binding
from .context import _binding, tenant_binding

logger = logging.getLogger(__name__)
_task_tokens = {}


def actor_kind(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return "anonymous"
    if getattr(user, "is_superuser", False) or getattr(user, "role", "") == "superadmin":
        return "superadmin"
    return "account"


def request_binding(request):
    path = getattr(request, "path_info", "") or ""
    kind = actor_kind(getattr(request, "user", None))
    for prefix, name in PATH_CAPABILITIES:
        if path.startswith(prefix):
            return capability_binding(name, label=prefix, actor_kind=kind)
    match = getattr(request, "resolver_match", None)
    url_name = getattr(match, "url_name", "") or ""
    if url_name in ROUTE_CAPABILITIES:
        return capability_binding(ROUTE_CAPABILITIES[url_name], label=url_name, actor_kind=kind)
    from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
    targets, _recognized = authoritative_route_resolution(request)
    targets = {value for value in targets if type(value) is int and value > 0}
    return tenant_binding(targets, label=url_name) if targets else None


def task_binding(task, args, kwargs):
    name = getattr(task, "name", "") or ""
    if name in TASK_CAPABILITIES:
        return capability_binding(TASK_CAPABILITIES[name], label=name, actor_kind="task")
    try:
        bound = inspect.signature(task.run).bind_partial(*(args or ()), **(kwargs or {}))
    except (TypeError, ValueError):
        return None
    makerspace_id = bound.arguments.get("makerspace_id")
    if type(makerspace_id) is int and makerspace_id > 0:
        return tenant_binding({makerspace_id}, label=name)
    return None


def on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **extra):
    try:
        binding = task_binding(task, args, kwargs)
    except Exception:
        logger.exception("tenant_rls_task_binding_failed")
        binding = None
    _task_tokens[task_id] = _binding.set(binding)


def on_task_postrun(task_id=None, **extra):
    token = _task_tokens.pop(task_id, None)
    from .report import flush
    from .wrapper import release_connections
    flush(label=getattr(extra.get("task"), "name", ""))
    if token is not None:
        _binding.reset(token)
    release_connections()
