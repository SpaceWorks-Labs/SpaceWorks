"""Fence the complete series projection before authority and waiter promotion."""

from apps.makerspaces.models import Makerspace
from apps.organizations.audience import lock_membership_sources, owned_space_ids

from .models import EventRegistration
from .organization_audience import AUDIENCE, AudienceChanged, candidate_ids
from .staff_grant_locks import authority_sources


def lock_series_admission_sources(series, occurrences, audience, actor):
    """Caller holds series -> occurrences; spaces must precede organizations/users.

    Occurrences can have their own organizer sets. Lock their union in one pass so
    later FIFO promotion cannot acquire an earlier space or account out of order.
    """
    if audience != AUDIENCE:
        return
    targets = [series, *[
        event for event in occurrences
        if "registration_audience" not in (event.series_override_fields or [])
    ]]
    candidates = [(target, candidate_ids(target)) for target in targets]
    organization_ids = set().union(*(ids for _, ids in candidates))
    space_ids = owned_space_ids(organization_ids) | {series.makerspace_id}
    list(Makerspace.objects.select_for_update().filter(pk__in=space_ids).order_by("pk"))

    def check_sources():
        for target, ids in candidates:
            if candidate_ids(target) != ids or not owned_space_ids(ids).issubset(space_ids):
                raise AudienceChanged()

    check_sources()
    # Authority can also derive from organizations outside the admission candidates.
    for target in targets:
        organization_ids.update(authority_sources(target)[3])
    user_ids = set(EventRegistration.objects.filter(
        event_id__in=[event.pk for event in targets[1:]],
    ).values_list("member_id", flat=True))
    user_ids.add(getattr(actor, "pk", None))
    lock_membership_sources(organization_ids, user_ids - {None}, space_ids)
    check_sources()
