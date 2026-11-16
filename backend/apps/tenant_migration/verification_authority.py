"""Target authority checks distinguish carried staff from imported members."""

from apps.accounts.models import User
from apps.accounts.staff_identity import person_q
from apps.makerspaces.models import MakerspaceMembership
from .identity_resolution import linked_authority_fingerprint
from .insertion_errors import ImportVerificationError, PrimaryKeyMapUnavailable

def _verify_authority(target, job, pk_map, identity_report):
    member_role = target.roles.get(slug="member")
    # Community rows only (chosen on purpose): a member's community row carries Member alone.
    memberships = MakerspaceMembership.track_manager(MakerspaceMembership.Track.COMMUNITY).filter(
        person_q("user__"), makerspace=target)
    if memberships.exclude(
        assigned_role=member_role,
        role=MakerspaceMembership.Role.CUSTOM,
    ).exists():
        raise ImportVerificationError("The import conferred authority beyond Member.")
    from .staff_postconditions import verify_staff_transport
    verify_staff_transport("default", target.pk)
    for decision in job.identity_decisions.iterator(chunk_size=500):
        try:
            target_id = pk_map.lookup(User, decision.source_user_id)
        except PrimaryKeyMapUnavailable:
            continue
        user = User.objects.get(pk=target_id)
        if decision.identity_resolution == decision.IdentityResolution.CREATE_WALK_IN:
            if user.is_superuser or user.is_staff or user.role != User.Role.REQUESTER:
                raise ImportVerificationError("An imported walk-in has global authority.")
    if (
        linked_authority_fingerprint(job, pk_map)
        != identity_report.linked_global_state_fingerprint
    ):
        raise ImportVerificationError(
            "The import mutated a linked identity's target-global authority."
        )


