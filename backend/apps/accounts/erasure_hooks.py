"""Optional subject erasure adapters; core accounts never imports a domain app."""
from contextlib import ExitStack, contextmanager

from django.db import transaction

from apps.encryption.account_write_fence import account_fences
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from apps.tenant_migration.gate_locks import shared_boundary

_hooks = {}


def register(name, provider):
    existing = _hooks.get(name)
    if existing is not None and existing != provider:
        raise ValueError("Duplicate account erasure provider.")
    _hooks[name] = provider


@contextmanager
def erasure_scope(user_id, *, actor):
    """Caller already authorized erasure; sources precede exclusive account fences.

    Each domain prepares only IDs without locks or keys. Revalidation runs before
    domain row locks. Adapters erase drafts/consent; submitted evidence stays owned
    by that domain. The enclosing transaction also removes the account vault.
    """
    prepared = [(provider, provider.discover(user_id)) for _, provider in sorted(_hooks.items())]
    tenants = sorted({pk for _, scope in prepared for pk in scope.tenant_ids})
    with ExitStack() as stack:
        stack.enter_context(shared_boundary(0))
        for tenant_id in tenants:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        stack.enter_context(account_fences([user_id], tenants, exclusive=True))
        # Account/key rows are handled first, before any domain Event lock. The
        # exclusive account fence covers both halves and rollback restores both.
        yield
        for provider, scope in prepared:
            provider.erase_locked(user_id, scope, actor=actor)
