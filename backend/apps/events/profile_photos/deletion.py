"""Ordered entry point for an already-authorized profile/membership deletion."""
from contextlib import ExitStack

from django.db import connection, transaction

from apps.encryption.account_write_fence import account_fences
from apps.events.credentials.errors import ProgrammeConflict


def _scope(kind, pk):
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.models_profiles import MemberProfile
    from .models import EventMemberPresentation
    if kind == "profile":
        source = MemberProfile.objects.get(pk=pk)
        membership = source.membership
        rows = EventMemberPresentation.objects.filter(selected_profile_id=pk)
    elif kind == "membership":
        membership = MakerspaceMembership.objects.get(pk=pk)
        rows = EventMemberPresentation.objects.filter(selected_membership_id=pk)
    else:
        raise ValueError("Unknown presentation source.")
    return (membership.pk, membership.user_id, membership.makerspace_id,
            tuple(rows.order_by("event_id", "pk").values_list("pk", "event_id", "event__makerspace_id", "event__series_id")))


def delete_source(kind, pk, *, actor=None):
    """Caller owns deletion permission. Invoke before starting a row transaction.

    The pre-delete receiver performs the paired update/audit in this transaction.
    The database trigger is the raw-SQL/concurrent-FK shape backstop.
    """
    if connection.in_atomic_block:
        raise RuntimeError("Discover source deletion scopes before domain transactions.")
    from apps.events.models_event import Event
    from apps.events.models_series import EventSeries
    from apps.makerspaces.models import Makerspace, MakerspaceMembership
    from apps.makerspaces.models_profiles import MemberProfile
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    from .models import EventMemberPresentation
    from .source_lifecycle import clear_selections

    prepared = _scope(kind, pk)
    membership_id, member_id, source_tenant, selections = prepared
    tenants = sorted({source_tenant, *(row[2] for row in selections)})
    with ExitStack() as stack:
        for tenant_id in tenants:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        stack.enter_context(account_fences([member_id], tenants, exclusive=True, allow_erased=True))
        if _scope(kind, pk) != prepared:
            raise ProgrammeConflict("Deletion sources changed. Retry the command.", code="subject_changed")
        list(EventSeries.objects.select_for_update().filter(pk__in={row[3] for row in selections if row[3]}).order_by("pk"))
        list(Event.objects.select_for_update().filter(pk__in={row[1] for row in selections}).order_by("pk"))
        list(Makerspace.objects.select_for_update().filter(pk__in=tenants).order_by("pk"))
        membership = MakerspaceMembership.objects.select_for_update().get(pk=membership_id)
        profiles = list(MemberProfile.objects.select_for_update().filter(membership=membership).order_by("pk"))
        if _scope(kind, pk) != prepared:
            raise ProgrammeConflict("Deletion sources changed.", code="subject_changed")
        clear_selections(EventMemberPresentation.objects.filter(pk__in=[row[0] for row in selections]), actor=actor)
        if kind == "membership":
            return membership.delete()
        source = next((profile for profile in profiles if profile.pk == pk), None)
        if source is None:
            raise ProgrammeConflict("Deletion source changed.", code="subject_changed")
        return source.delete()
