from types import SimpleNamespace

from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from tests.accounts.reauth_helpers import force_recent_authenticate
from .p1_helpers import staff

PASSWORD = "Separate staff password 684!"


def context(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    root = User.objects.create_superuser("p3-root", email="root@example.test", password=PASSWORD)
    space = Makerspace.objects.create(name="P3", slug="p3")
    other = Makerspace.objects.create(name="Other", slug="p3-other")
    manager, _ = staff(space, "p3-manager", role="space_manager", password=PASSWORD)
    peer, _ = staff(space, "p3-peer", role="space_manager", password=PASSWORD)
    worker, membership = staff(space, "p3-worker", password=PASSWORD)
    foreign, _ = staff(other, "p3-foreign", role="space_manager", password=PASSWORD)
    member = User.objects.create_user("p3-member", password=PASSWORD)
    return SimpleNamespace(root=root, space=space, other=other, manager=manager, peer=peer,
                           worker=worker, membership=membership, foreign=foreign, member=member)


def client(actor, *, recent=True):
    result = APIClient()
    if recent:
        force_recent_authenticate(result, actor)
    else:
        from apps.accounts.tokens import SpaceWorksRefreshToken
        result.force_authenticate(actor, token=SpaceWorksRefreshToken.for_user(actor).access_token)
    return result


def base(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/"
