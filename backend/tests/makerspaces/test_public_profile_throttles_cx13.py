"""549 retains the shared account-keyed lookup budgets of decision 336b/c."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.throttles import FixedWindowRateThrottle
from tests.makerspaces.test_public_profile_cx13 import BASE, person

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("authentication", ["force", "jwt"])
@pytest.mark.parametrize("scope,rate", [("profile_lookup", "2/min"), ("profile_lookup_daily", "2/day")])
def test_handle_and_by_account_share_exhaustion_but_other_accounts_do_not(person, monkeypatch, scope, rate, authentication):
    cache.clear()
    monkeypatch.setitem(FixedWindowRateThrottle.THROTTLE_RATES, scope, rate)
    monkeypatch.setattr(FixedWindowRateThrottle, "timer", staticmethod(lambda: 2_000_030.0))
    other = User.objects.create_user(username="cx13-other-budget")
    account_profile_for(other)
    def signed_in(user):
        api = APIClient()
        if authentication == "force":
            api.force_authenticate(user)
        else:
            from apps.accounts.tokens import SpaceWorksRefreshToken
            token = SpaceWorksRefreshToken.for_user(user).access_token
            token["surface"] = "member"
            api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return api

    viewer = signed_in(other)
    # A miss on the rich by-account reader spends the same budget as a handle read.
    miss = viewer.get("/api/v1/profiles/by-account/999999999/")
    assert miss.status_code == 404
    assert miss.data["code"] == "not_found"
    assert viewer.get(BASE).status_code == 200
    refused = viewer.get(BASE)
    assert refused.status_code == 429
    assert refused.data["code"] == "throttled"
    by_account = viewer.get(f"/api/v1/profiles/by-account/{person.pk}/")
    assert by_account.status_code == 429
    assert by_account.data["code"] == "throttled"
    independent = signed_in(person)
    assert independent.get(BASE).status_code == 200
    assert APIClient().get(BASE).status_code == 200
    cache.clear()


@pytest.mark.parametrize("failure", ["expired", "restricted"])
def test_optional_session_failure_does_not_close_the_card(person, failure):
    from apps.accounts.tokens import SpaceWorksRefreshToken
    token = SpaceWorksRefreshToken.for_user(person).access_token
    token["surface"] = "member"
    if failure == "expired":
        token.set_exp(lifetime=-timedelta(minutes=1))
    else:
        User.objects.filter(pk=person.pk).update(access_status="restricted")
    response = APIClient().get(BASE, HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    expected = {"display_name": "Maker 名", "avatar_url": None}
    if failure == "expired":
        expected.update(handle="cx13.maker", bio="Builds useful things", projects=[], memberships=[])
    assert response.data == expected
