"""Authority, scope and page identity are prepared before event/source row locks.

Decision #86 merges the two event-website write designs. This layer (events programme)
runs first, outside any domain transaction: it re-reads the actor, declares the write
scope (tenant keys, event credentials and tenant gates for every tenant/account the
event touches) and pre-allocates the EventPage primary key. Object bytes are then
reserved, journalled and written by ``event_asset_transaction`` (Pages), which replays
the locked domain operation and attaches each verified object in one commit.
"""
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps

from django.db import connection
from rest_framework.exceptions import ValidationError

from apps.events import event_authority
from apps.events.event_permissions import VIEW, EDIT_DETAILS, PUBLISH_SCHEDULE
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .models import Event, EventSeries
from .models_website import EventPage
from .website_copy import owner
from .website_visibility import effective_page
from .clone_preparation import page_identity
from apps.transaction_guards import in_domain_transaction

_prepared = ContextVar("prepared_website_write", default=None)


@dataclass
class PreparedWrite:
    page_source: tuple | None
    prepared_page_id: int | None


def current_page(target):
    return EventPage.objects.filter(series=target).first() if isinstance(target, EventSeries) else effective_page(target)


def _fresh_actor(actor):
    """Authority is decided on the current account row, never the request's cached
    instance: a deactivated or suspended actor must not reach upload bytes."""
    from rest_framework.exceptions import PermissionDenied
    from apps.accounts.models import User
    fresh = User.objects.filter(pk=actor.pk).first() if actor is not None else None
    if not event_authority._active(fresh):
        raise PermissionDenied()
    return fresh


def _declared_scope(target, actor):
    """The same tenant/account/event declaration ``event_write`` locks, discovered early."""
    from .programme_locks import event_scopes
    if isinstance(target, EventSeries):
        event_ids = tuple(Event.objects.filter(series_id=target.pk).order_by("pk").values_list("pk", flat=True))
    else:
        event_ids = (target.pk,)
    tenants, accounts = {target.makerspace_id}, {actor.pk}
    for event_id in event_ids:
        ts, ac = event_scopes(event_id=event_id)
        tenants.update(ts)
        accounts.update(ac)
    return event_ids, tuple(sorted(tenants)), tuple(sorted(accounts))


def _prepare(target, actor):
    event_authority.require(actor, target, VIEW)
    if not (event_authority.can(actor, target, EDIT_DETAILS) or event_authority.can(actor, target, PUBLISH_SCHEDULE)):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()
    page = current_page(target)
    own = EventPage.objects.filter(**owner(target)).first()
    if own:
        page_id = own.pk
    else:
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [EventPage._meta.db_table])
            page_id = cursor.fetchone()[0]
    return PreparedWrite(page_source=page_identity(page), prepared_page_id=page_id)


def prepared_page_write(callback):
    @wraps(callback)
    def wrapped(target, *, actor, **kwargs):
        if in_domain_transaction():
            raise RuntimeError("Prepare website assets before domain transactions.")
        actor = _fresh_actor(actor)
        event_ids, tenants, _accounts = _declared_scope(target, actor)
        with ExitStack() as stack:
            from apps.encryption.preparation import prepare_tenants
            from .credentials.preparation import prepare_event_credentials
            stack.enter_context(prepare_tenants(tenants))
            stack.enter_context(prepare_event_credentials(event_ids))
            for tenant_id in tenants:
                stack.enter_context(boundary_tenant_write(tenant_id))
            token = _prepared.set(_prepare(target, actor))
            try:
                return callback(target, actor=actor, **kwargs)
            finally:
                _prepared.reset(token)
    return wrapped


def prepared_page_id():
    prepared = _prepared.get()
    return prepared.prepared_page_id if prepared is not None else None


@contextmanager
def prepared_copies(target):
    """Inside the locked operation: refuse a page that changed since preparation."""
    prepared = _prepared.get()
    if prepared is None or prepared.page_source != page_identity(current_page(target)):
        raise ValidationError("The website changed. Retry resource preparation.")
    yield prepared
