"""Seeded presence subjects without replacing guards, serializers or services."""
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.models_account_profile import AccountProfile, AccountProject
from apps.presence.models import PresencePreference, PresenceSession, PresenceSettings
from tests.payments.account_helpers import make_payer
from tests.presence.fence_helpers import fence


def seed(space, person, *, session=True):
    fence(space)
    PresenceSettings.objects.get_or_create(makerspace=space)
    preference = PresencePreference.objects.create(makerspace=space, account=person)
    profile, _ = AccountProfile.objects.get_or_create(user=person)
    project = AccountProject.objects.create(profile=profile, title="G6 private project", public_visible=False)
    membership = MakerspaceMembership.objects.filter(makerspace=space, user=person).first()
    row = None
    if session:
        now = timezone.now()
        row = PresenceSession.objects.create(makerspace=space, account=person, member=person,
            membership=membership, status="visiting" if membership else "guest",
            started_at=now - timedelta(minutes=5), expires_at=now + timedelta(minutes=55))
    return row, preference, project


def member(space):
    return make_payer("g6-present-" + uuid4().hex[:8], space)
