from datetime import datetime, timezone as dt_timezone

import pytest
from django.utils import timezone
from apps.accounts.models import User
from apps.makerspaces.models import AccountProfile, Makerspace, MakerspaceMembership
from apps.makerspaces.profile_services import save_profile
from apps.makerspaces.public_profile_handles import claim_handle


@pytest.fixture
def membership(settings):
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    settings.ALLOWED_HOSTS = ["testserver", "localhost", ".example.test"]
    space = Makerspace.objects.create(name="Profile lab", slug="contract-profile", timezone="Asia/Kolkata",
                                     public_site_enabled=True)
    user = User.objects.create_user(username="contract-maker", email="private@example.test", display_name="A Maker")
    return MakerspaceMembership.objects.create(makerspace=space, user=user,
        role="custom", assigned_role=space.roles.get(slug="member"), verified_at=timezone.now(),
        activated_at=datetime(2025, 1, 2, tzinfo=dt_timezone.utc))


@pytest.fixture
def published(membership):
    profile = save_profile(membership, {})
    # Decision 549 removed these writes; seed retained historical satellite consent explicitly.
    AccountProfile.objects.filter(pk=profile.pk).update(is_visible=True, public_visible=True,
                                                       public_consented_at=timezone.now())
    claim_handle(membership.user, "public.maker")
    profile.refresh_from_db()
    # Written for the per-membership profile; the global profile keeps ONE membership reachable.
    profile.membership = membership
    return profile
