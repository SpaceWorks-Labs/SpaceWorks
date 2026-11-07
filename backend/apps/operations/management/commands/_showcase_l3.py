"""Populate the real member-card list in every fresh or reset fictional showcase."""
from apps.makerspaces.member_card_services import issue_card
from apps.makerspaces.models import MakerspaceMembership, MemberCard

from . import _showcase_data as data


def seed_member_cards(space, manager, members):
    for username, _display_name in data.MEMBERS:
        user = members[username]
        membership = MakerspaceMembership.objects.get(
            makerspace=space, user=user, status="active")
        if not MemberCard.objects.filter(membership=membership, revoked_at__isnull=True).exists():
            issue_card(manager, membership, printed_name=user.display_name)
