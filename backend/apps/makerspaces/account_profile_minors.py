"""Minors and co-membership on the global profile (SECURITY-REVIEW H4, decision 336a/b).

A person is a minor when any space recorded them as one (an uncleared `MinorProfile` that is still
under that space's age of majority). Their global profile is never platform-wide: only the person
and members of one of the minor's own spaces read it, and the open web additionally needs a
CURRENT guardian consent in every space that recorded them (the existing guardian flow). The
minors switch of a space is deliberately not consulted: switching the feature off does not make a
child an adult, so the check fails closed.

`shares_space` is also the "co-member" test of decision 336b: people who share an active space see
role titles and vouches; everyone else sees only what is public about the person.
"""

from .models import MakerspaceMembership


def minor_rows(user):
    from .community_policy import policy_for
    from .minors import is_minor
    from .models import MinorProfile

    rows = MinorProfile.objects.filter(user_id=user.pk, cleared_at__isnull=True).select_related("makerspace")
    return [row for row in rows if is_minor(row, policy_for(row.makerspace))]


def is_minor_account(user):
    return bool(minor_rows(user))


def guardian_consented(user):
    """True when every space that recorded the person as a minor holds a current guardian consent."""
    from .minors import current_consent

    return all(current_consent(row) is not None for row in minor_rows(user))


def active_space_ids(user):
    return set(MakerspaceMembership.all_tracks.filter(user_id=user.pk, status="active")
               .values_list("makerspace_id", flat=True))


def shared_space_ids(user, viewer):
    """Spaces where BOTH are active members; empty for an anonymous or missing viewer."""
    if viewer is None or not getattr(viewer, "is_authenticated", False) or viewer.pk is None:
        return set()
    return active_space_ids(user) & active_space_ids(viewer)


def shares_space(user, viewer):
    return bool(shared_space_ids(user, viewer))
