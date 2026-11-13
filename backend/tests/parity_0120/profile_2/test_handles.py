"""Default handle (305c + addendum): the username only when available, otherwise none."""
import pytest

from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.models import PublicHandle

from .conftest import make_person

pytestmark = pytest.mark.django_db


def test_username_claimed_when_available():
    user = make_person("grace_h")
    account_profile_for(user)
    assert PublicHandle.objects.get(user=user).handle == "grace_h"


@pytest.mark.parametrize("username", ["ab", "admin", "bad name!"])
def test_no_handle_when_username_does_not_fit_or_is_reserved(username):
    user = make_person(username.replace(" ", "").replace("!", "") if username == "bad name!" else username)
    user.username = username
    user.save(update_fields=["username"])
    account_profile_for(user)
    assert not PublicHandle.objects.filter(user=user).exists()


def test_no_generated_fallback_when_username_taken():
    first = make_person("taken_name")
    account_profile_for(first)
    second = make_person("other")
    second.username = "Taken_Name"
    second.save(update_fields=["username"])
    account_profile_for(second)
    assert not PublicHandle.objects.filter(user=second).exists()
    # the member can still choose one later, and is reachable by account id meanwhile
    from apps.makerspaces.public_profile_handles import claim_handle
    assert claim_handle(second, "my-own-name").handle == "my-own-name"
