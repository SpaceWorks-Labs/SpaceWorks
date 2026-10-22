"""The inert requester principals that historical account-less loan requests point at.

Account-less requests were removed (#75f) and nothing creates a principal any more, but
requests filed before then keep theirs, so reports must still recognise and exclude it.
"""

from apps.makerspaces.models import Makerspace


def anonymous_requester_ids(makerspace_ids=None):
    """The sentinel user ids, for excluding them from per-PERSON aggregates.

    Every account-less request in a makerspace points at ONE principal, so any report
    that groups by `requester_id` folds every unrelated stranger into a single fictional
    human -- one "repeat offender", one "top borrower". That row is not a person: it
    cannot be contacted, cannot be ranked against real borrowers, and must never be
    restricted (doing so would restrict every future account-less requester at once,
    which is why `accounts.principal_guards.refuse_anonymous_requester_access_mutation`
    exists). Reports exclude these ids instead.

    One query. `makerspace_ids=None` means every makerspace, which is what the
    organization-wide rankings need.
    """
    queryset = Makerspace.objects.exclude(anonymous_requester__isnull=True)
    if makerspace_ids is not None:
        queryset = queryset.filter(pk__in=makerspace_ids)
    return set(queryset.values_list("anonymous_requester_id", flat=True))
