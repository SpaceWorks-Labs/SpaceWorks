"""A community membership row for a fixture user (staff accounts hold a staff-track row, which is not dues' subject)."""
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import make_membership


def community_membership(makerspace, user):
    row = MakerspaceMembership.objects.filter(makerspace=makerspace, user=user).first()
    return row or make_membership(user, makerspace)
