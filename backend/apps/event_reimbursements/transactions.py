"""Source → PII fences → series/event → host → authority → domain parents."""
from contextlib import contextmanager
from django.db import transaction
from apps.accounts import rbac
from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.claim_sessions import claim_context
from apps.accounts.reauthentication import binding, require_recent_reauth
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events import event_authority
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event, EventSeries, EventCommandReceipt, EventCollaborator, EventRegistration, HackathonApplication
from apps.events.programme.commands import fingerprint
from apps.events.programme_locks import fences, lock_authority
from apps.events.staged_forms.transactions import Context, changed, require_outer
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
from apps.payments.event_payouts.errors import require
from apps.presence.guard import require_active_principal
from apps.tenant_migration.gate_runtime import boundary_tenant_write, assert_write_allowed


def require_reimbursement_locked(space):
    from rest_framework.exceptions import ValidationError
    try:
        return require_module_locked(space, "event_reimbursements")
    except ValidationError:
        require(False, "reimbursement_unavailable")


def check_origin(request, event, *, owner=False):
    origin = origin_scoped_makerspace_id(request)
    if origin is None or origin == event.makerspace_id:
        return
    allowed = owner and (EventCollaborator.objects.filter(event=event, makerspace_id=origin, status="accepted").exists()
        or EventRegistration.objects.filter(event=event, member=request.user, registered_via_makerspace_id=origin).exists())
    require(allowed, "not_found", status=404)


def authorize(actor, event, *, owner=False, finance=False, permission=None, request=None):
    require(getattr(actor, "account_kind", None) in ("member", "staff", "platform"), "full_session_required", status=403)
    require(claim_context(actor) is None, "full_session_required", status=403)
    require_active_principal(actor, event.makerspace)
    require(not actor.must_change_password, "full_session_required", status=403)
    if request is not None:
        require(getattr(request, "api_client", None) is None, "full_session_required", status=403)
        binding(request)
        check_origin(request, event, owner=owner)
    if owner:
        require_member_account(actor)
        require(not MakerspaceMembership.objects.filter(user=actor, makerspace_id=event.makerspace_id)
                .exclude(status="active").exists(), "account_restricted", status=403)
        participation = EventRegistration.objects.filter(event=event, member=actor).exists() or \
            HackathonApplication.objects.filter(event=event, member=actor).exists()
        if not participation:
            require(event.is_public and event.status == "published", "not_found", status=404)
            from apps.events.registration_access import require_registration_access
            origin = origin_scoped_makerspace_id(request) if request is not None else None
            via = Makerspace.objects.get(pk=origin) if origin is not None and origin != event.makerspace_id else None
            require_registration_access(event, actor, collaborative=via is not None, via=via)
    elif finance:
        require(rbac.can(actor, rbac.Action.VIEW_FINANCE, event.makerspace_id), "finance_required", status=403)
        require(request is not None, "full_session_required", status=403)
        request.user = actor
        require_recent_reauth(request)
    else:
        event_authority.require(actor, event, permission)


@contextmanager
def prepared_boundary(makerspace_id):
    # The lock-only source boundary is held during broker/key preparation, but
    # no application row locks or domain transaction have started yet.
    with boundary_tenant_write(makerspace_id):
        key = prepare_tenant_key(makerspace_id)
        with tenant_key_context(key):
            yield


@contextmanager
def command(*, event_id, actor, data, action, permission=None, owner=False,
            finance=False, request=None, account_ids=(), additional_event_ids=()):
    seed = Event.objects.select_related("makerspace").get(pk=event_id)
    event_ids = tuple(sorted({event_id, *additional_event_ids}))
    seeds = list(Event.objects.filter(pk__in=event_ids, makerspace_id=seed.makerspace_id).order_by("pk"))
    require(len(seeds) == len(event_ids), "not_found", status=404)
    series_ids = tuple(sorted({row.series_id for row in seeds if row.series_id}))
    authorize(actor, seed, owner=owner, finance=finance, permission=permission, request=request)
    assert_write_allowed(seed.makerspace_id)
    tenants = tuple(sorted({seed.makerspace_id, *EventCollaborator.objects.filter(event_id__in=event_ids,
        status="accepted").values_list("makerspace_id", flat=True)}))
    accounts = tuple(sorted(set((actor.pk, *account_ids))))
    digest = fingerprint({"action": action, "body": data})
    with prepared_boundary(seed.makerspace_id), transaction.atomic(), fences(
        tenant_ids=tenants, account_ids=accounts,
    ):
        list(EventSeries.objects.select_for_update().filter(pk__in=series_ids).order_by("pk"))
        locked_events = {row.pk: row for row in Event.objects.select_for_update(of=("self",)).filter(pk__in=event_ids).order_by("pk")}
        require(all(row.pk in locked_events and locked_events[row.pk].makerspace_id == seed.makerspace_id
            and locked_events[row.pk].series_id == row.series_id for row in seeds), "scope_changed")
        event = locked_events[seed.pk]
        require((event.makerspace_id, event.series_id) == (seed.makerspace_id, seed.series_id), "scope_changed")
        current_tenants = tuple(sorted({event.makerspace_id, *EventCollaborator.objects.filter(event_id__in=event_ids,
            status="accepted").values_list("makerspace_id", flat=True)}))
        require(current_tenants == tenants, "scope_changed")
        spaces = {row.pk: row for row in Makerspace.objects.select_for_update().filter(pk__in=tenants).order_by("pk")}
        space = spaces[event.makerspace_id]
        event.makerspace = require_module_locked(space, "events")
        require_reimbursement_locked(space)
        actor = lock_authority(actor, event)
        require(actor is not None, "account_inactive", status=403)
        authorize(actor, event, owner=owner, finance=finance, permission=permission, request=request)
        receipt = EventCommandReceipt.objects.filter(event=event, actor=actor,
            operation_uuid=data["operation_id"]).first()
        require(receipt is None or receipt.request_sha256 == digest, "idempotency_conflict")
        if not action.startswith("programme.") and receipt is None:
            from .config_models import ReimbursementProgramme
            programme = ReimbursementProgramme.objects.filter(event=event).first()
            require(programme is not None and programme.enabled and not programme.imported_paused, "reimbursement_unavailable")
        yield Context(event, actor, data, digest, LockedContext(event_id=event.pk,
            tenant_ids=tenants, account_ids=accounts), receipt)
