"""Source gates and predeclared PII/account fences for existing event services."""
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature

from django.db import transaction

from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models import Event, EventSeries
from .programme_locks import event_scopes, fences, lock_authority

_held = ContextVar("event_service_write_boundary", default=None)
SCOPE_RETRIES = 3


@contextmanager
def write_boundary(target, *, actor=None, account_ids=(), tenant_ids=()):
    """Discover without locks, then fence, lock resources, and revalidate scope.

    A series command declares every occurrence before taking the series lock.
    Nested service calls may reuse this declaration, never add an earlier class.
    """
    from apps.makerspaces.models import Makerspace
    from .programme.commands import ProgrammeConflict

    is_series = isinstance(target, EventSeries)
    series_id = target.pk if is_series else Event.objects.values_list("series_id", flat=True).get(pk=target.pk)
    event_ids = tuple(Event.objects.filter(series_id=series_id).order_by("pk").values_list("pk", flat=True)) if is_series else (target.pk,)
    tenants, accounts = set(tenant_ids) | {target.makerspace_id}, set(account_ids)
    if actor is not None:
        accounts.add(actor.pk)
    for event_id in event_ids:
        ts, ac = event_scopes(event_id=event_id)
        tenants.update(ts)
        accounts.update(ac)
    declaration = (tuple(sorted(tenants)), tuple(sorted(accounts)))
    held = _held.get()
    if held is not None:
        if (not set(event_ids) <= held[0] or not tenants <= set(held[1][0])
                or not accounts <= set(held[1][1])):
            raise ProgrammeConflict("scope_changed", "Write scope changed. Retry the whole command.")
        yield
        return
    with ExitStack() as stack:
        from apps.encryption.preparation import prepare_tenants
        stack.enter_context(prepare_tenants(declaration[0]))
        from .credentials.preparation import prepare_event_credentials
        stack.enter_context(prepare_event_credentials(event_ids))
        for tenant_id in declaration[0]:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        stack.enter_context(fences(tenant_ids=declaration[0], account_ids=declaration[1]))
        if series_id:
            EventSeries.objects.select_for_update().get(pk=series_id)
        events = list(Event.objects.select_for_update().filter(pk__in=event_ids).order_by("pk"))
        if is_series and tuple(Event.objects.filter(series_id=series_id).order_by("pk").values_list("pk", flat=True)) != event_ids:
            raise ProgrammeConflict("scope_changed", "Series occurrences changed. Retry the command.")
        for event in events:
            ts, ac = event_scopes(event_id=event.pk)
            if not set(ts) <= tenants or not set(ac) <= accounts or (not is_series and event.series_id != series_id):
                raise ProgrammeConflict("scope_changed", "Event participants changed. Retry the command.")
        list(Makerspace.objects.select_for_update().filter(pk__in=tenants).order_by("pk"))
        for event in events:
            ts, ac = event_scopes(event_id=event.pk)
            if not set(ts) <= tenants or not set(ac) <= accounts:
                raise ProgrammeConflict("scope_changed", "Event participants changed. Retry the command.")
        for resource in ([target] if is_series else events):
            lock_authority(actor, resource)
        from .hackathons.admission_models import HackathonConfig
        from .hackathons.admission_transactions import lock_domain_parents
        for event in events:
            list(HackathonConfig.objects.select_for_update().filter(event=event).order_by("pk"))
            lock_domain_parents(event.pk)
        token = _held.set((set(event_ids), declaration))
        try:
            yield
        finally:
            _held.reset(token)


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
