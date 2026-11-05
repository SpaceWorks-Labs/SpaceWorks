import logging
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar

from django.db import transaction
from django.utils import timezone

from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.gate_locks import acquire_shared, shared_boundary
from apps.tenant_migration.models_source_gate import SourceMigrationGate


_archive_authority = ContextVar("source_migration_archive_authority", default=None)
_boundary_shared_locks = ContextVar("source_gate_boundary_shared_locks", default=())
logger = logging.getLogger(__name__)


def assert_write_allowed(makerspace_id):
    """Lock and validate in either a service transaction or a gate boundary."""
    makerspace_id = int(makerspace_id)
    # A boundary already protects all application transactions through commit.
    # Reacquiring on another connection can queue behind an exclusive waiter that
    # is itself waiting for our boundary, so consult boundary ownership FIRST.
    if makerspace_id in _boundary_shared_locks.get():
        _assert_gate_state(makerspace_id)
        return
    if transaction.get_connection().in_atomic_block:
        acquire_shared(makerspace_id)
        _assert_gate_state(makerspace_id)
        return
    # A direct non-transactional assertion is supported for boundary-style callers.
    # Request/task boundaries use ``boundary_tenant_write`` so this same lock remains
    # held after validation and through their entire dispatch.
    with shared_boundary(makerspace_id):
        _assert_gate_state(makerspace_id)


def _assert_gate_state(makerspace_id):
    _assert_source_gate_state(makerspace_id)
    # #185: the same single check refuses writes to a paused or read-only space.
    from apps.space_controls.write_policy import assert_space_writable
    assert_space_writable(makerspace_id)


def _assert_source_gate_state(makerspace_id):
    gate = SourceMigrationGate.objects.only(
        "state", "purpose", "owner_id", "fencing_token", "lease_expires_at"
    ).filter(makerspace_id=makerspace_id).first()
    if gate is None or gate.state == SourceMigrationGate.State.OPEN:
        return
    authority = _archive_authority.get()
    if (
        authority == (int(makerspace_id), gate.owner_id, gate.fencing_token)
        and gate.lease_expires_at is not None
        and gate.lease_expires_at > timezone.now()
    ):
        return
    raise SourceMigrationGateClosed(
        "This makerspace is temporarily frozen for tenant migration.",
        purpose=gate.purpose,
    )


@contextmanager
def boundary_tenant_write(makerspace_id):
    """Validate under a dedicated lock transaction without transacting dispatch."""
    makerspace_id = int(makerspace_id)
    if makerspace_id in _boundary_shared_locks.get():
        assert_write_allowed(makerspace_id)
        yield
        return
    with shared_boundary(makerspace_id):
        token = _boundary_shared_locks.set(
            _boundary_shared_locks.get() + (makerspace_id,)
        )
        try:
            assert_write_allowed(makerspace_id)
            yield
        finally:
            _boundary_shared_locks.reset(token)


@contextmanager
def fanout_tenant_write(makerspace_id, *, operation, counts):
    """Hold one tenant boundary, or report a frozen item and let the scan continue."""
    makerspace_id = int(makerspace_id)
    from apps.space_controls.write_policy import fanout_context
    with ExitStack() as stack:
        # #185: paused spaces skip every sweep; read-only spaces skip sweeps that create.
        stack.enter_context(fanout_context(operation))
        try:
            stack.enter_context(boundary_tenant_write(makerspace_id))
        except SourceMigrationGateClosed:
            counts["skipped"] = counts.get("skipped", 0) + 1
            logger.info(
                "tenant_fanout_skipped_closed_source_gate",
                extra={"makerspace_id": makerspace_id, "operation": operation},
            )
            yield False
            return
        # --- lane L8: one tenant of a scheduled sweep runs under that tenant's RLS scope.
        from apps.tenant_rls.context import tenant_context
        stack.enter_context(tenant_context(makerspace_id, label=operation))
        yield True


def assert_request_write_allowed(request, user=None):
    """Late DRF guard for tenants resolved only after parsing/authentication."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    # #195: the authenticated actor confirms (superadmin) or revokes a pending bypass.
    from apps.space_controls.superadmin_bypass import confirm
    confirm(user)
    from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
    from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
    from apps.tenant_migration.gate_policy import HTTP_EXEMPTIONS

    match = getattr(request, "resolver_match", None)
    if getattr(match, "view_name", None) in HTTP_EXEMPTIONS:
        return
    targets, route_recognized = authoritative_route_resolution(request)
    if targets:
        # URL/model ownership is authoritative. Client hints are intentionally not
        # consulted here: a conflicting hint remains the view's validation error, but
        # cannot select a different tenant lock or bypass a closed source gate.
        for makerspace_id in sorted(targets):
            assert_write_allowed(makerspace_id)
        return
    if route_recognized:
        # Known-but-unresolvable routes are not tenant writes yet. Preserve the
        # eventual view error and rely on the unscoped request-boundary lock.
        return
    try:
        makerspace_id = origin_scoped_makerspace_id(request)
    except Exception:
        return
    if isinstance(makerspace_id, int):
        assert_write_allowed(makerspace_id)


@contextmanager
def tenant_write(makerspace_id):
    """Hold the shared advisory lock from validation through transaction commit."""
    with transaction.atomic():
        assert_write_allowed(makerspace_id)
        yield


@contextmanager
def source_archive_write(makerspace_id, owner_id, fencing_token):
    token = _archive_authority.set(
        (int(makerspace_id), owner_id, int(fencing_token))
    )
    try:
        with tenant_write(makerspace_id):
            yield
    finally:
        _archive_authority.reset(token)
