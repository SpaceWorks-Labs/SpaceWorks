"""Source gates and predeclared PII/account fences for existing event services."""
from django.utils.translation import gettext
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature

from django.db import transaction

from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models import Event, EventSeries
from .programme_locks import event_scopes, fences, lock_authority
from .staff_grant_locks import authority_sources

_held = ContextVar("event_service_write_boundary", default=None)
SCOPE_RETRIES = 3


def _authority_declaration(resources):
    return {(resource._meta.label_lower, resource.pk): tuple(sorted(authority_sources(resource)[3]))
            for resource in resources}


@contextmanager
def write_boundary(target, *, actor=None, account_ids=(), tenant_ids=(), nowait_makerspaces=False,
                   additional_event_ids=(), allow_cross_tenant=False):
    """Discover without locks, then fence, lock resources, and revalidate scope.

    A series command declares every occurrence before taking the series lock.
    Nested service calls may reuse this declaration, never add an earlier class.
    Cross-tenant batches must authorize every row before entering this boundary.
    """
    from apps.makerspaces.models import Makerspace
    from .programme.commands import ProgrammeConflict

    is_series = isinstance(target, EventSeries)
    series_id = target.pk if is_series else Event.objects.values_list("series_id", flat=True).get(pk=target.pk)
    primary_ids = tuple(Event.objects.filter(series_id=series_id).order_by("pk").values_list("pk", flat=True)) if is_series else (target.pk,)
    event_ids = primary_ids
    if additional_event_ids:
        if is_series:
            raise ProgrammeConflict("scope_changed", gettext("Write scope changed. Retry the whole command."))
        requested_ids = set(primary_ids) | set(additional_event_ids)
        requested = Event.objects.filter(pk__in=requested_ids)
        if not allow_cross_tenant:
            requested = requested.filter(makerspace_id=target.makerspace_id)
        event_ids = tuple(requested.order_by("pk").values_list("pk", flat=True))
        if set(event_ids) != requested_ids:
            raise ProgrammeConflict("scope_changed", gettext("Write scope changed. Retry the whole command."))
    event_series = dict(Event.objects.filter(pk__in=event_ids).values_list("pk", "series_id")) if additional_event_ids else {}
    tenants, accounts = set(tenant_ids) | {target.makerspace_id}, set(account_ids)
    event_tenants, event_accounts = {}, {}
    if actor is not None:
        accounts.add(actor.pk)
    for event_id in event_ids:
        ts, ac = event_scopes(event_id=event_id)
        event_tenants[event_id] = set(ts)
        event_accounts[event_id] = set(ac)
        tenants.update(ts)
        accounts.update(ac)
    declaration = (tuple(sorted(tenants)), tuple(sorted(accounts)))
    resources = [target] if is_series else list(Event.objects.filter(pk__in=event_ids).order_by("pk"))
    authority = _authority_declaration(resources)
    held = _held.get()
    if held is not None:
        if nowait_makerspaces:
            raise ProgrammeConflict("scope_changed", gettext("Start the decision as a fresh transaction."))
        if (not set(event_ids) <= held[0] or not tenants <= set(held[1][0])
                or not accounts <= set(held[1][1])):
            raise ProgrammeConflict("scope_changed", gettext("Write scope changed. Retry the whole command."))
        yield
        return
    # The declaration is reusable only inside its transaction AND fences.
    # Clear it before either exits, including before Django runs on_commit.
    with ExitStack() as stack:
        from apps.encryption.preparation import prepare_tenants
        from apps.encryption.crypto import PiiUnavailable
        try:
            stack.enter_context(prepare_tenants(declaration[0]))
        except PiiUnavailable as exc:
            tenant_id = getattr(exc, "preparation_tenant_id", None)
            # Discovery may have found a new dependency since a batch preflight.
            # Carry its event identity too, without exposing either in the API.
            exc.preparation_event_id = next((pk for pk, ts in event_tenants.items() if tenant_id in ts), None)
            raise
        from .credentials.preparation import prepare_event_credentials
        stack.enter_context(prepare_event_credentials(event_ids))
        for tenant_id in declaration[0]:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        from apps.encryption.write_fence import PiiWriteFenced
        try:
            stack.enter_context(fences(tenant_ids=declaration[0], account_ids=declaration[1]))
        except PiiWriteFenced as exc:
            tenant_id = getattr(exc, "fence_tenant_id", None)
            account_id = getattr(exc, "fence_account_id", None)
            exc.preparation_event_id = next((pk for pk in event_ids
                if tenant_id in event_tenants[pk] or account_id in event_accounts[pk]), None)
            raise
        if additional_event_ids:
            series_ids = sorted({value for value in event_series.values() if value is not None})
            locked_series = list(EventSeries.objects.select_for_update().filter(pk__in=series_ids).order_by("pk"))
            if len(locked_series) != len(series_ids):
                raise ProgrammeConflict("scope_changed", gettext("Write scope changed. Retry the whole command."))
        elif series_id:
            EventSeries.objects.select_for_update().get(pk=series_id)
        events = list(Event.objects.select_for_update().filter(pk__in=event_ids).order_by("pk"))
        if additional_event_ids and {event.pk: event.series_id for event in events} != event_series:
            raise ProgrammeConflict("scope_changed", gettext("Write scope changed. Retry the whole command."))
        if is_series and tuple(Event.objects.filter(series_id=series_id).order_by("pk").values_list("pk", flat=True)) != primary_ids:
            raise ProgrammeConflict("scope_changed", gettext("Series occurrences changed. Retry the command."))
        for event in events:
            ts, ac = event_scopes(event_id=event.pk)
            if not set(ts) <= tenants or not set(ac) <= accounts or (not is_series and event.pk == target.pk and event.series_id != series_id):
                raise ProgrammeConflict("scope_changed", gettext("Event participants changed. Retry the command."))
        list(Makerspace.objects.select_for_update(nowait=nowait_makerspaces, of=("self",)).filter(pk__in=tenants).order_by("pk"))
        for event in events:
            ts, ac = event_scopes(event_id=event.pk)
            if not set(ts) <= tenants or not set(ac) <= accounts:
                raise ProgrammeConflict("scope_changed", gettext("Event participants changed. Retry the command."))
        resources = [target] if is_series else events
        if _authority_declaration(resources) != authority:
            raise ProgrammeConflict("scope_changed", gettext("Write scope changed. Retry the whole command."))
        # All organization sources precede per-resource authority rows, including
        # batches whose events list shared organizations in different orders.
        from apps.organizations.models import Organization
        organization_ids = {pk for ids in authority.values() for pk in ids}
        list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
        for resource in resources:
            lock_authority(actor, resource)
        from .hackathons.admission_models import HackathonConfig
        from .hackathons.admission_transactions import lock_domain_parents
        for event in events:
            list(HackathonConfig.objects.select_for_update().filter(event=event).order_by("pk"))
            lock_domain_parents(event.pk)
        token = _held.set((set(event_ids), declaration))
        stack.callback(_held.reset, token)
        yield


def event_write(function=None, *, permission=False):
    """Wrap existing signatures without changing their public service imports."""
    if function is None:
        return lambda callback: event_write(callback, permission=permission)
    parameters = signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        # A concurrent command (another member registering) can grow the event's
        # discovered scope between discovery and the lock. Nothing was written yet, so
        # an outermost command re-discovers and retries instead of failing with 409.
        from .programme.commands import ProgrammeConflict
        attempts = 1 if _held.get() is not None else SCOPE_RETRIES
        for attempt in range(attempts):
            try:
                return run(*args, **kwargs)
            except ProgrammeConflict as exc:
                if attempt + 1 == attempts or str(exc.detail.get("code")) != "scope_changed":
                    raise

    def run(*args, **kwargs):
        bound = parameters.bind(*args, **kwargs)
        values = bound.arguments
        target = next((values[key] for key in ("event", "registration", "series", "target") if key in values), None)
        if not isinstance(target, (Event, EventSeries)):
            target = Event.objects.get(pk=target.event_id)
        member, via = values.get("member"), values.get("via_makerspace")
        with write_boundary(target, actor=values.get("actor"),
                            account_ids=(member.pk,) if member else (), tenant_ids=(via.pk,) if via else ()):
            from apps.accounts.models import User
            from . import event_authority
            from apps.accounts.claim_sessions import carry_claim_context
            actor = values.get("actor")
            if actor is not None:
                actor = carry_claim_context(actor, User.objects.filter(pk=actor.pk).first())
                if not event_authority._active(actor):
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied()
                bound.arguments["actor"] = actor
            if member is not None:
                bound.arguments["member"] = carry_claim_context(member, User.objects.get(pk=member.pk))
            fresh = type(target).objects.get(pk=target.pk)
            if permission is not False:
                event_authority.require(actor, fresh, permission)
            for key in ("event", "series", "target"):
                if key in values:
                    bound.arguments[key] = fresh
            return function(*bound.args, **bound.kwargs)
    return wrapped
