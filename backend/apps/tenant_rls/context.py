"""The one RLS binding a request, task or command runs under (#75d, #120).

A binding is either a tenant scope (the makerspace ids rows must belong to) or one
registered cross-tenant capability. No binding means the context is OPEN: policies admit
every row, exactly as before RLS. Rollout stage 1 binds every tenant-addressed request,
every per-tenant task boundary and every registered cross-tenant path; everything else
stays open and is narrowed in later stages (docs/INVARIANTS.md "Row-level security").

The innermost binding wins, and leaving a binding always releases the connection state
it left behind (``wrapper.release_connections``).
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_binding = ContextVar("tenant_rls_binding", default=None)


@dataclass(frozen=True)
class Binding:
    scope: frozenset = frozenset()
    capability: str = ""
    label: str = ""

    def guc_values(self, mode):
        """The four transaction-local settings the policies read."""
        ids = "" if self.capability else ",".join(str(value) for value in sorted(self.scope))
        return {
            "app.rls_bound": "on",
            "app.makerspace_id": ids,
            "app.rls_capability": self.capability,
            "app.rls_mode": mode,
        }


def current():
    return _binding.get()


@contextmanager
def bind(binding):
    """Run the block under ``binding`` (``None`` = open), restoring the outer one after."""
    token = _binding.set(binding)
    try:
        yield binding
    finally:
        _binding.reset(token)
        from .wrapper import release_connections
        release_connections()


def activate(binding):
    """Set the binding for the rest of an enclosing ``bind()`` block (middleware use)."""
    _binding.set(binding)


def tenant_binding(makerspace_ids, *, label=""):
    ids = frozenset(makerspace_ids)
    if not ids or any(type(value) is not int or value < 1 for value in ids):
        raise ValueError("A tenant RLS binding needs persisted makerspace ids.")
    return Binding(scope=ids, label=label)


def tenant_context(makerspace_ids, *, label=""):
    """Bind to one or more tenants: rows of every other tenant are invisible."""
    if isinstance(makerspace_ids, int):
        makerspace_ids = (makerspace_ids,)
    return bind(tenant_binding(makerspace_ids, label=label))


def capability_context(name, *, label="", actor_kind="system"):
    """Bind to a registered cross-tenant capability (audited, sampled)."""
    from .capabilities import capability_binding
    return bind(capability_binding(name, label=label, actor_kind=actor_kind))
