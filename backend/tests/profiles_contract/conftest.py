import pytest
from django.utils import timezone
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
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
        role="custom", assigned_role=space.roles.get(slug="member"), verified_at=timezone.now())


@pytest.fixture
def published(membership):
    profile = save_profile(membership, {"public_visible": True, "publication_consent": True})
    claim_handle(membership, "public.maker")
    profile.refresh_from_db()
    return profile
