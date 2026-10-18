"""The R boundary: source, prepared crypto, fences, event, authority, R parents.

The caller prepares form/account values before entering. Replays are checked
after live authorization and before compare-and-swap. References contain IDs only.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from django.db import transaction
from django.utils import timezone
from apps.accounts import rbac
from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.claim_sessions import claim_context
from apps.makerspaces.models import MakerspaceMembership
from apps.accounts.reauthentication import require_recent_reauth
from apps.audit.services import record
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events import event_authority
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event, EventSeries, EventCommandReceipt, EventRegistration, HackathonApplication
from apps.events.programme.commands import fingerprint
from apps.events.programme_locks import fences, lock_authority
from apps.makerspaces.guards import require_module_locked
from apps.payments.event_payouts.errors import require
from apps.presence.guard import require_active_account
from apps.tenant_migration.gate_runtime import boundary_tenant_write, assert_write_allowed


@dataclass
class Context:
    event: object
    actor: object
    data: dict = field(repr=False)
    digest: str
    locks: LockedContext
    receipt: object

    @property
    def replay(self):
        return self.receipt.response_reference if self.receipt else None

    def cas(self, row, expected=None):
        require(row.version == (self.data["expected_version"] if expected is None else expected),
                "stale_version", current_version=row.version)

    def finish(self, row, **extra):
        reference = {"id": str(row.pk) if not isinstance(row.pk, int) else row.pk,
                     "version": row.version, "state": getattr(row, "state", "configured"), **extra}
        EventCommandReceipt.objects.create(event=self.event, actor=self.actor,
            operation_uuid=self.data["operation_id"], request_sha256=self.digest,
            response_reference=reference)
        return reference

    def audit(self, action, row, **meta):
        record(self.actor, action, makerspace=self.event.makerspace, target=row, meta=meta)


@contextmanager
def command(*, event_id, actor, data, action, permission=None, owner=False,
            finance=False, request=None, reimbursement=False, account_ids=()):
    seed = Event.objects.select_related("makerspace").get(pk=event_id)
    if owner:
        require_member_account(actor)
        require_active_account(actor, seed.makerspace)
        require(claim_context(actor) is None, "full_session_required", status=403)
        require(EventRegistration.objects.filter(event=seed, member=actor).exists() or
                HackathonApplication.objects.filter(event=seed, member=actor).exists(),
                "canonical_participation_required")
    if finance:
        require(request is not None and request.user.pk == actor.pk, "full_session_required", status=403)
        require_recent_reauth(request)
        require(rbac.can(actor, rbac.Action.VIEW_FINANCE, seed.makerspace_id), "finance_required", status=403)
    elif not owner:
        event_authority.require(actor, seed, permission)
    assert_write_allowed(seed.makerspace_id)
    key = prepare_tenant_key(seed.makerspace_id)
    accounts = tuple(sorted(set((actor.pk, *account_ids))))
    digest = fingerprint({"action": action, "body": data})
    with boundary_tenant_write(seed.makerspace_id), tenant_key_context(key), transaction.atomic(), fences(
        tenant_ids=(seed.makerspace_id,), account_ids=accounts,
    ):
        if seed.series_id:
            EventSeries.objects.select_for_update().get(pk=seed.series_id)
        event = Event.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=seed.pk)
        require((event.makerspace_id, event.series_id) == (seed.makerspace_id, seed.series_id), "scope_changed")
        event.makerspace = require_module_locked(event.makerspace, "events")
        if reimbursement:
            require_module_locked(event.makerspace, "event_reimbursements")
        actor = lock_authority(actor, event)
        require(actor is not None, "account_inactive", status=403)
        if owner:
            require_member_account(actor)
            require_active_account(actor, event.makerspace)
            require(claim_context(actor) is None, "full_session_required", status=403)
            require(not MakerspaceMembership.objects.filter(user=actor, makerspace=event.makerspace).exclude(status="active").exists(),
                    "account_restricted", status=403)
        elif finance:
            require(rbac.can(actor, rbac.Action.VIEW_FINANCE, event.makerspace_id), "finance_required", status=403)
            request.user = actor
            require_recent_reauth(request)
        else:
            event_authority.require(actor, event, permission)
        receipt = EventCommandReceipt.objects.filter(event=event, actor=actor,
            operation_uuid=data["operation_id"]).first()
        require(receipt is None or receipt.request_sha256 == digest, "idempotency_conflict")
        yield Context(event, actor, data, digest,
            LockedContext(event_id=event.pk, tenant_ids=(event.makerspace_id,), account_ids=accounts), receipt)


def changed(row, **values):
    for key, value in values.items():
        setattr(row, key, value)
    row.version += 1
    row.save()
    return row


def require_outer(locks, event):
    from apps.events.programme_locks import assert_lock_context
    assert_lock_context(locks)
    require(locks.event_id == event.pk and event.makerspace_id in locks.tenant_ids, "invalid_subject", status=404)
