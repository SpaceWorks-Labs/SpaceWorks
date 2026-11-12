"""One source/fence/event/authority boundary for every lane A command."""
from django.utils.translation import gettext
import hashlib
import json
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from django.apps import apps
from django.db import transaction
from django.shortcuts import get_object_or_404
from apps.audit import services as audit
from apps.events import event_authority
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event
from apps.events.registration_access import require_registration_access
from apps.makerspaces.platform import feature_enabled
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .admission_errors import fail
from .admission_models import HackathonConfig
from .admission_ports import ports


@dataclass
class CommandContext:
    event: object
    config: HackathonConfig
    actor: object
    locks: LockedContext
    receipt: object
    reference: dict | None
    created_config: bool = False
    input_sha256: str = ""

    def finish(self, kind, pk, *, status=200, **metadata):
        self.receipt.response_reference = {**metadata, "kind": kind, "id": pk, "status": status, "input_sha256": self.input_sha256}
        self.receipt.save(update_fields=["response_reference"])


def require_member(actor):
    from apps.accounts.account_kind_guards import require_member_account
    require_member_account(actor)
    if not actor.is_active or actor.access_status != "active" or getattr(actor, "is_tenant_dump_stub", False):
        fail("account_inactive", gettext("An active member account is required."), status=403)


def admission_enabled(makerspace):
    """Hackathons, or applications for any one-off event (#128 C-32), open the admission engine."""
    return feature_enabled(makerspace, "events.hackathons") or feature_enabled(makerspace, "events.applications")


def require_programme(event):
    if not admission_enabled(event.makerspace):
        fail("not_found", gettext("Not found."), status=404)
    config = get_object_or_404(HackathonConfig, event=event, enabled=True)
    return config


def member_event(actor, event_id, makerspace_id):
    require_member(actor)
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=event_id, makerspace_id=makerspace_id)
    ports().context_gate(event=event, actor=actor)
    require_registration_access(event, actor)
    return event, require_programme(event)


def record(ctx, action, target, **meta):
    audit.record(ctx.actor, "event.hackathon." + action, makerspace=ctx.event.makerspace,
                 target=target, meta=meta)


def notice(ctx, application, kind):
    # Provider inserts a durable envelope/work item in this transaction. It may
    # enqueue on_commit; no SMTP/chat/network I/O is permitted here.
    ports().enqueue_notice(event_id=ctx.event.pk, member_id=application.member_id,
                           application_id=application.pk, revision=application.version, kind=kind)
    if kind.startswith("application_"):
        # Lane L21a: the status also reaches staff rooms and webhooks, IDs only.
        from .admission_webhooks import application_changed
        application_changed(ctx.event, application, kind)


def lock_accounts(integration, event, accounts):
    if integration.lock_actor is None:
        return {}
    from apps.accounts.models import User
    return {candidate.pk: integration.lock_actor(candidate, event)
            for candidate in User.objects.filter(pk__in=accounts).order_by("pk")}


@contextmanager
def command(*, event_id, actor, data, action, permission=None, owner=False, account_ids=(), configuration=False, normalized_body=None):
    integration = ports()
    event = get_object_or_404(Event, pk=event_id)
    if owner:
        require_member(actor)
    else:
        event = event_authority.get_event(actor, event_id, permission)
    tenants, accounts = integration.event_scopes(event_id=event_id, account_ids=tuple(sorted(set((*account_ids, actor.pk)))))
    tenants, accounts = tuple(sorted(set(tenants))), tuple(sorted(set(accounts)))
    if event.makerspace_id not in tenants or actor.pk not in accounts:
        raise RuntimeError("Incomplete admission fence declaration.")
    integration.assert_encryption_ready(event_id=event_id)
    def hashed(body):
        return hashlib.sha256(json.dumps({"action": action, "body": body}, sort_keys=True,
                                         separators=(",", ":"), default=str).encode()).hexdigest()
    input_digest = hashed(data)
    digest = hashed(data if normalized_body is None else normalized_body)
    from apps.events.services_write_boundary import write_boundary
    from apps.events.programme_locks import current_locks
    with ExitStack() as stack:
        stack.enter_context(write_boundary(event, actor=actor, tenant_ids=tenants, account_ids=accounts))
        held = current_locks(event_id)
        tenants, accounts = held.tenant_ids, held.account_ids
        locked = Event.objects.select_related("makerspace").get(pk=event_id)
        if locked.pk != event_id or locked.makerspace_id != event.makerspace_id:
            raise RuntimeError("Event scope changed; restart before acquiring locks.")
        if integration.lock_actor is not None:
            actor = lock_accounts(integration, locked, accounts).get(actor.pk)
            if actor is None:
                fail("account_inactive", gettext("An active account is required."), status=403)
        if owner:
            require_member(actor)
            integration.context_gate(event=locked, actor=actor)
            require_registration_access(locked, actor)
        else:
            event_authority.require(actor, locked, permission)
        created_config = False
        if configuration:
            if not admission_enabled(locked.makerspace):
                fail("not_found", gettext("Not found."), status=404)
            config, created_config = HackathonConfig.objects.get_or_create(event=locked, defaults={
                "attendance_required": integration.default_attendance_required(event=locked)})
        else:
            config = require_programme(locked)
        config = HackathonConfig.objects.select_for_update().get(pk=config.pk)
        lock_domain_parents(event_id)
        receipt_model = apps.get_model("events", "EventCommandReceipt")
        receipt = receipt_model.objects.filter(event_id=event_id, actor_id=actor.pk,
                                                operation_uuid=data["operation_id"]).first()
        if receipt and receipt.request_sha256 != digest and (receipt.response_reference or {}).get("input_sha256") != input_digest:
            fail("idempotency_conflict", gettext("This operation was already used for different input."))
        if receipt is None:
            receipt = receipt_model.objects.create(event_id=event_id, actor_id=actor.pk,
                operation_uuid=data["operation_id"], request_sha256=digest, response_reference=None)
        ctx = CommandContext(locked, config, actor,
            LockedContext(event_id=event_id, tenant_ids=tenants, account_ids=accounts),
            receipt, receipt.response_reference, created_config, input_digest)
        yield ctx


def assert_locked(locks, event_id):
    if not isinstance(locks, LockedContext) or locks.event_id != event_id or not transaction.get_connection().in_atomic_block:
        raise RuntimeError("An existing event lock context is required.")


def lock_domain_parents(event_id):
    # Event serialization makes this stable. Parents precede all application,
    # review and membership children, including downstream eligibility repair.
    from apps.events.models import EventTicketType, EventInvite, EventPromoCode
    from .team_models import HackathonTeam
    from .admission_models import HackathonApplicationCohort
    list(EventTicketType.objects.select_for_update().filter(event_id=event_id).order_by("pk"))
    list(EventInvite.objects.select_for_update().filter(event_id=event_id).order_by("pk"))
    list(EventPromoCode.objects.select_for_update().filter(event_id=event_id).order_by("pk"))
    list(HackathonTeam.objects.select_for_update().filter(event_id=event_id).order_by("pk"))
    list(HackathonApplicationCohort.objects.select_for_update().filter(event_id=event_id).order_by("pk"))
