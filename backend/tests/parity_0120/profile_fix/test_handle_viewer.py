"""`/public/page-handles/<handle>/` is viewer-aware: signed-in members resolve non-open-web profiles."""
import pytest

from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.models import PublicHandle
from tests.parity_0120.profile_fix.conftest import client_for, make_person, make_space

pytestmark = pytest.mark.django_db
URL = "/api/v1/public/page-handles/{}/"


@pytest.fixture
def ada():
    return make_person("ada", make_space("space-a"))


@pytest.fixture
def grace():
    return make_person("grace", make_space("space-b"))


def handle_of(user):
    account_profile_for(user)
    return PublicHandle.objects.get(user=user).handle


def test_signed_in_member_resolves_a_non_open_web_profile(ada, grace):
    handle = handle_of(ada)
    response = client_for(grace).get(URL.format(handle))
    assert response.status_code == 200 and response.data["kind"] == "member"
    assert "private" in response["Cache-Control"] and "no-store" in response["Cache-Control"]


def test_logged_out_visitor_still_gets_404_for_the_same_handle(ada):
    handle = handle_of(ada)
    response = client_for().get(URL.format(handle))
    assert response.status_code == 404


def test_open_web_profile_resolves_logged_out(ada):
    handle = handle_of(ada)
    save_profile(ada, {"public_visible": True, "publication_consent": True})
    assert client_for().get(URL.format(handle)).status_code == 200


def test_hidden_profile_is_404_for_both(ada, grace):
    handle = handle_of(ada)
    save_profile(ada, {"is_visible": False})
    assert client_for(grace).get(URL.format(handle)).status_code == 404
    assert client_for().get(URL.format(handle)).status_code == 404


def test_share_card_resolution_stays_anonymous(ada, grace):
    from apps.makerspaces.public_page_access import resolve_handle
    from rest_framework.exceptions import NotFound

    handle = handle_of(ada)
    with pytest.raises(NotFound):
        resolve_handle(handle)  # no viewer: open-web only, as PublicPageShareView calls it
