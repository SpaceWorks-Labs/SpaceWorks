"""Discover cross-tenant presentation source dependencies before purge row locks."""
from contextlib import ExitStack, contextmanager

from django.apps import apps
from django.db import connection, transaction
from django.db.models import Q


def _snapshot(tenant_id):
    try:
        model = apps.get_model("events", "EventMemberPresentation")
    except LookupError:
        return ()  # Optional Events removal must never strand a core purge.
    return tuple(model.objects.filter(
        Q(selected_membership__makerspace_id=tenant_id)
        | Q(selected_profile__membership__makerspace_id=tenant_id)
    ).order_by("pk").values_list("pk", "member_id", "event_id", "event__makerspace_id", "event__series_id"))


@contextmanager
def presentation_purge_scope(tenant_id, *, actor=None):
    from apps.encryption.account_write_fence import account_fences
    from apps.makerspaces.models import Makerspace
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    prepared = _snapshot(tenant_id)
    if not prepared:
        yield
        return
    from apps.events.credentials.errors import ProgrammeConflict
    from .source_lifecycle import clear_selections
    Event = apps.get_model("events", "Event")
    EventSeries = apps.get_model("events", "EventSeries")
    EventMemberPresentation = apps.get_model("events", "EventMemberPresentation")
    if connection.in_atomic_block:
        raise RuntimeError("Discover presentation purge scope before row transactions.")
    tenants = tuple(sorted({tenant_id, *(row[3] for row in prepared)}))
    accounts = tuple(sorted({row[1] for row in prepared}))
    with ExitStack() as stack:
        for pk in tenants:
            stack.enter_context(boundary_tenant_write(pk))
        stack.enter_context(transaction.atomic())
        stack.enter_context(account_fences(accounts, tenants, exclusive=True, allow_erased=True))
        list(EventSeries.objects.select_for_update().filter(pk__in={row[4] for row in prepared if row[4]}).order_by("pk"))
        list(Event.objects.select_for_update().filter(pk__in={row[2] for row in prepared}).order_by("pk"))
        list(Makerspace.objects.select_for_update().filter(pk__in=tenants).order_by("pk"))
        if _snapshot(tenant_id) != prepared:
            raise ProgrammeConflict("Presentation sources changed. Retry purge.", code="subject_changed")
        clear_selections(EventMemberPresentation.objects.filter(pk__in=[row[0] for row in prepared]), actor=actor)
        yield
