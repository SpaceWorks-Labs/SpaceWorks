"""Registry scope checks shared by signed and publishable client admission."""

from apps.inventory.middleware_observability import (
    TARGET_UNRESOLVED, TENANT_MISMATCH, failure_reason, scope_failure_reason, set_failure_reason,
)


class ClientScopeMixin:
    def _signed_target_hidden(self, request, client):
        from apps.apiclients import scope_registry

        entry = scope_registry.lookup(scope_registry.resolve_view_name(request), request.method)
        if entry is None or entry.target_mode == scope_registry.TARGET_GLOBAL:
            return False
        if not scope_registry.scope_allows(entry, client.scopes):
            return False
        if entry.server_only and client.client_type != "server":
            return False
        if entry.tenant_bound and client.makerspace_id is None:
            return False
        if client.client_type == "peer" and not scope_registry.peer_may_reach(entry, request.method):
            return False
        return failure_reason(request) in (TARGET_UNRESOLVED, TENANT_MISMATCH)

    def _client_scope_ok(self, request, client):
        from apps.apiclients import scope_registry

        entry = scope_registry.lookup(
            scope_registry.resolve_view_name(request), request.method
        )
        if entry is None:
            set_failure_reason(request, TARGET_UNRESOLVED)
            return False
        target, resolved = scope_registry.resolve_target_once(request, entry)
        allowed = scope_registry.target_allows(entry, client, target, resolved)
        if not allowed:
            reason = TARGET_UNRESOLVED if not resolved else TENANT_MISMATCH
            set_failure_reason(request, reason)
        return allowed

    def _makerspace_scope_ok(self, request, makerspace):
        from apps.apiclients import scope_registry

        entry = scope_registry.lookup(
            scope_registry.resolve_view_name(request), request.method
        )
        if entry is None:
            set_failure_reason(request, TARGET_UNRESOLVED)
            return False
        target, resolved = scope_registry.resolve_target_once(request, entry)
        if entry.target_mode == scope_registry.TARGET_GLOBAL:
            return True
        if not resolved:
            set_failure_reason(request, TARGET_UNRESOLVED)
            return False
        allowed = getattr(target, "pk", None) == makerspace.pk
        if not allowed:
            set_failure_reason(request, TENANT_MISMATCH)
        return allowed

    def _request_scope_ok(self, request, client):
        from apps.apiclients import scope_registry

        observation = scope_registry.classify(request, client)
        if not observation.verdict:
            set_failure_reason(request, scope_failure_reason(observation, client))
        return observation.verdict

    def _scope_checks_ok(self, request, client):
        request_scope_ok = self._request_scope_ok(request, client)
        return request_scope_ok and self._client_scope_ok(request, client)
