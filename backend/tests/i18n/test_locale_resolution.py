import pytest
from django.test import RequestFactory
from django.utils import translation
from rest_framework.test import APIClient

from config import locale_resolution as lr
from config.locale_registry import canonicalize, locale_list_payload, supported_codes


class _User:
    def __init__(self, preferred_locale=None):
        self.preferred_locale = preferred_locale


class _Space:
    pk = 1

    def __init__(self, default_locale="en"):
        self.default_locale = default_locale


def test_registry():
    assert supported_codes() == ("en",)
    assert locale_list_payload() == [{"code": "en", "label": "English"}]
    for value in ("en", "EN", "en-US", "en_gb", " en "):
        assert canonicalize(value) == "en"
    for value in ("", None, "fr", "en,fr", "e", "123", "en-"):
        assert canonicalize(value) is None


def test_source_precedence_even_with_one_locale():
    assert lr.resolve(explicit="en", user=_User("en"), makerspace=_Space(), ambient="en") == ("en", lr.EXPLICIT)
    assert lr.resolve(user=_User("en"), makerspace=_Space(), ambient="en") == ("en", lr.USER)
    assert lr.resolve(user=_User(None), makerspace=_Space(), ambient="en") == ("en", lr.MAKERSPACE)
    assert lr.resolve(user=_User(None), ambient="en-US") == ("en", lr.ACCEPT_LANGUAGE)
    assert lr.resolve() == ("en", lr.SYSTEM)
    assert lr.resolve(explicit="fr", ambient="de") == ("en", lr.SYSTEM)


@pytest.mark.parametrize("header", ["", "fr", "en,fr", "en;q=1", "x" * 40])
def test_bad_dedicated_header_is_never_explicit(header):
    request = RequestFactory().get("/", HTTP_X_SPACEWORKS_LOCALE=header, HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
    assert lr.preliminary(request) == ("en", lr.ACCEPT_LANGUAGE)


def test_dedicated_header_outranks_ambient():
    request = RequestFactory().get("/", HTTP_X_SPACEWORKS_LOCALE="EN", HTTP_ACCEPT_LANGUAGE="fr")
    assert lr.preliminary(request) == ("en", lr.EXPLICIT)


def test_makerspace_replaces_only_ambient_or_system():
    request = RequestFactory().get("/")
    lr.apply(request, "en", lr.ACCEPT_LANGUAGE)
    lr.activate_resolved_makerspace_locale(request, _Space())
    assert request.locale_source == lr.MAKERSPACE
    for kept in (lr.EXPLICIT, lr.USER):
        lr.apply(request, "en", kept)
        lr.activate_resolved_makerspace_locale(request, _Space())
        assert request.locale_source == kept
    translation.deactivate()


@pytest.mark.django_db
def test_makerspace_id_costs_no_query_on_one_locale(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert lr.makerspace_default(123) == "en"


def test_background_override_restores():
    translation.activate("en")
    with lr.override_for(user=_User(None), makerspace=_Space()) as code:
        assert code == "en" and translation.get_language() == "en"
    assert translation.get_language() == "en"


@pytest.mark.django_db
def test_responses_carry_content_language_and_vary():
    response = APIClient().get("/api/v1/health/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9",
                               HTTP_X_SPACEWORKS_LOCALE="en")
    assert response["Content-Language"] == "en"
    vary = response["Vary"].lower()
    assert "accept-language" in vary and "x-spaceworks-locale" in vary


@pytest.mark.django_db
def test_cors_preflight_allows_the_locale_header(settings):
    response = APIClient().options(
        "/api/v1/health/", HTTP_ORIGIN="http://localhost:5000",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-spaceworks-locale",
    )
    assert "x-spaceworks-locale" in response.get("Access-Control-Allow-Headers", "").lower()


@pytest.mark.django_db
def test_recovery_refusal_is_localized_and_does_not_leak():
    from apps.backup.models import DeploymentRecoveryState
    from django.urls import reverse
    state = DeploymentRecoveryState.load()
    state.mode = DeploymentRecoveryState.Mode.QUARANTINED
    state.save(update_fields=("mode", "updated_at"))
    client = APIClient()
    for _ in range(2):
        response = client.get(reverse("auth-login"), HTTP_X_SPACEWORKS_LOCALE="en")
        assert response.status_code == 503
        assert response["Content-Language"] == "en"
        assert "x-spaceworks-locale" in response["Vary"].lower()
        assert response.json()["code"] == "deployment_quarantined"
