"""A membership-less account can set an avatar: `account/<user_id>/...` keys, charged to no space."""
import pytest
from django.db import transaction
from django.urls import reverse

from apps.makerspaces import profile_images
from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.account_profile_purge import purge_account_profile, without_account_held
from apps.makerspaces.models import AccountProfile, Makerspace
from apps.makerspaces.storage_key_collectors import collect_public_image_keys
from tests.parity_0120.profile_fix.conftest import client_for, make_person, make_space

pytestmark = pytest.mark.django_db
URL = "member-global-profile-image"
BODY = {"filename": "me.png", "content_type": "image/png"}


def test_membership_less_account_gets_an_account_key_and_can_attach_it(storage):
    user = make_person("loner")  # no membership at all
    client = client_for(user)
    presign = client.post(reverse(URL), BODY, format="json")
    assert presign.status_code == 201
    key = presign.data["object_key"]
    assert key.startswith(f"account/{user.pk}/") and key.endswith(".png")
    attach = client.put(reverse(URL), {"object_key": key}, format="json")
    assert attach.status_code == 200
    assert attach.data["avatar_url"].endswith(key)
    assert AccountProfile.objects.get(user=user).avatar_key == key


def test_account_key_is_not_attachable_by_another_account(storage):
    owner, other = make_person("owner"), make_person("other")
    key = client_for(owner).post(reverse(URL), BODY, format="json").data["object_key"]
    response = client_for(other).put(reverse(URL), {"object_key": key}, format="json")
    assert response.status_code == 400


def test_account_key_cannot_be_held_by_two_profiles(storage):
    one, two = make_person("one"), make_person("two")
    key = client_for(one).post(reverse(URL), BODY, format="json").data["object_key"]
    assert client_for(one).put(reverse(URL), {"object_key": key}, format="json").status_code == 200
    AccountProfile.objects.filter(user=two).delete()
    assert client_for(two).put(reverse(URL), {"object_key": key}, format="json").status_code == 400


def test_account_key_is_charged_to_no_space(storage):
    space = make_space("unrelated")
    before = Makerspace.objects.get(pk=space.pk).storage_bytes_used
    user = make_person("free")
    key = client_for(user).post(reverse(URL), BODY, format="json").data["object_key"]
    client_for(user).put(reverse(URL), {"object_key": key}, format="json")
    assert profile_images.space_for_key(key) is None
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == before
    assert key not in collect_public_image_keys(space)


def test_account_key_is_deleted_on_account_profile_purge(storage, django_capture_on_commit_callbacks):
    user = make_person("leaver")
    key = client_for(user).post(reverse(URL), BODY, format="json").data["object_key"]
    client_for(user).put(reverse(URL), {"object_key": key}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        purge_account_profile(user)
    assert key in storage
    assert not AccountProfile.objects.filter(user=user).exists()


def test_without_account_held_keeps_account_keys_out_of_space_purges():
    user = make_person("held")
    profile = account_profile_for(user)
    profile.avatar_key = f"account/{user.pk}/a.png"
    profile.save(update_fields=["avatar_key"])
    assert without_account_held([profile.avatar_key]) == []


def test_member_with_a_home_space_still_mints_and_attaches_member_keys(storage):
    space = make_space("home")
    user = make_person("resident", space)
    client = client_for(user)
    key = client.post(reverse(URL), BODY, format="json").data["object_key"]
    assert key.startswith(f"member/{space.pk}/")
    assert client.put(reverse(URL), {"object_key": key}, format="json").status_code == 200
    assert profile_images.space_for_key(key).pk == space.pk


def test_legacy_member_key_of_a_space_the_account_belongs_to_still_attaches(storage):
    space = make_space("legacy")
    user = make_person("old", space)
    key = f"member/{space.pk}/legacy.png"
    assert client_for(user).put(reverse(URL), {"object_key": key}, format="json").status_code == 200


def test_member_key_of_a_foreign_space_is_still_rejected(storage):
    mine, foreign = make_space("mine"), make_space("foreign")
    user = make_person("guest", mine)
    response = client_for(user).put(reverse(URL), {"object_key": f"member/{foreign.pk}/x.png"}, format="json")
    assert response.status_code == 400


def test_build_object_key_knows_the_account_kind():
    from apps.inventory import public_image_storage as pis

    assert pis.build_object_key("account", 7, ".png").startswith("account/7/")
