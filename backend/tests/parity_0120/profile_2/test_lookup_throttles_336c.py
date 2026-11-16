"""Decision 336(b)/(c), SECURITY-REVIEW H5/M15: profile lookups and handle checks have their own budgets.

`/profiles/by-account/<id>/` could be walked 1..N by any signed-in account; it is now limited per ACCOUNT (a
refused or missing id spends the budget too). Signed-in handle reads share that budget; signed-out handle reads
keep `public_read`. The username availability check is limited per account, or per IP when signed out.
"""
import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.makerspaces import throttles
from apps.makerspaces.account_profile_views import ProfileByAccountView
from apps.makerspaces.public_profile_views import PublicProfileView

from .conftest import client_for

pytestmark = pytest.mark.django_db
RATES = throttles.FixedWindowRateThrottle.THROTTLE_RATES
CHECK = "/api/v1/handles/check"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setattr(throttles.FixedWindowRateThrottle, "timer", staticmethod(lambda: 2_000_030.0))


def by_account(user_id):
    return f"/api/v1/profiles/by-account/{user_id}/"


def test_walking_account_ids_is_cut_off_per_account(monkeypatch, ada, grace, stranger):
    monkeypatch.setitem(RATES, "profile_lookup", "3/min")
    walker = client_for(stranger)
    first = [walker.get(by_account(ada.pk + offset)).status_code for offset in range(3)]
    assert 429 not in first                                   # normal reads (and misses) are answered
    assert walker.get(by_account(grace.pk)).status_code == 429
    assert client_for(grace).get(by_account(ada.pk)).status_code != 429   # another account is unaffected


def test_the_daily_budget_also_applies(monkeypatch, ada, stranger):
    monkeypatch.setitem(RATES, "profile_lookup_daily", "2/day")
    walker = client_for(stranger)
    assert [walker.get(by_account(ada.pk)).status_code == 429 for _ in range(3)] == [False, False, True]


def test_signed_in_handle_reads_share_the_account_budget_and_signed_out_reads_do_not(ada):
    assert throttles.ProfileLookupThrottle in PublicProfileView.throttle_classes
    assert throttles.ProfileLookupDailyThrottle in PublicProfileView.throttle_classes
    assert list(ProfileByAccountView.throttle_classes) == [throttles.ProfileLookupThrottle,
                                                           throttles.ProfileLookupDailyThrottle]
    factory = APIRequestFactory()
    anonymous = Request(factory.get("/api/v1/public/profiles/someone/"))
    assert throttles.ProfileLookupThrottle().get_cache_key(anonymous, None) is None
    signed_in = factory.get("/api/v1/public/profiles/someone/")
    force_authenticate(signed_in, user=ada)
    key = throttles.ProfileLookupThrottle().get_cache_key(Request(signed_in), None)
    assert key.endswith(f"user:{ada.pk}")


def test_the_handle_check_is_limited_per_ip_when_signed_out(monkeypatch):
    monkeypatch.setitem(RATES, "handle_check", "2/min")
    anonymous = client_for()
    assert anonymous.get(CHECK, {"handle": "free-name"}).status_code == 200
    assert anonymous.get(CHECK, {"handle": "other-name"}).status_code == 200
    assert anonymous.get(CHECK, {"handle": "third-name"}).status_code == 429
    assert anonymous.get(CHECK, {"handle": "x-name"}, REMOTE_ADDR="198.51.100.20").status_code == 200


def test_the_handle_check_counts_an_authenticated_caller_per_account(monkeypatch, ada, grace):
    monkeypatch.setitem(RATES, "handle_check", "1/min")
    assert client_for(ada).get(CHECK, {"handle": "free-name"}).status_code == 200
    assert client_for(ada).get(CHECK, {"handle": "free-name"}).status_code == 429
    assert client_for(grace).get(CHECK, {"handle": "free-name"}).status_code == 200
