"""Release 0.12.0 U2: the social sign-in start accepts only a same-origin relative `next`."""
import pytest

from apps.accounts.safe_next import validate_next_path
from apps.accounts.serializers_github import GithubBrowserStartSerializer
from apps.accounts.serializers_oidc_browser import OidcBrowserStartSerializer
from rest_framework import serializers

_NONCE = "a" * 43


@pytest.mark.parametrize("value", ["/dashboard", "/m/space/loans?tab=open", "/a/b#section"])
def test_relative_paths_are_accepted(value):
    assert validate_next_path(value) == value


@pytest.mark.parametrize("value", [
    "https://evil.example/x", "//evil.example", "/\\evil.example", "javascript:alert(1)", "dashboard",
    "/%2F%2Fevil.example", "/ok\nSet-Cookie: x=1", "/" + "a" * 600,
])
def test_open_redirect_shapes_are_refused(value):
    with pytest.raises(serializers.ValidationError):
        validate_next_path(value)


def test_start_serializers_expose_next_as_next_path_and_it_is_optional():
    github = GithubBrowserStartSerializer(data={"redirect_uri": "https://app.example/cb", "nonce": _NONCE,
                                                "next": "/loans"})
    assert github.is_valid(), github.errors
    assert github.validated_data["next_path"] == "/loans"
    oidc = OidcBrowserStartSerializer(data={"redirect_uri": "https://app.example/cb"})
    assert oidc.is_valid(), oidc.errors
    assert "next_path" not in oidc.validated_data
    bad = OidcBrowserStartSerializer(data={"redirect_uri": "https://app.example/cb", "next": "//evil.example"})
    assert not bad.is_valid() and "next" in bad.errors


@pytest.mark.django_db
def test_attempt_stores_next_and_the_callback_row_returns_it():
    from apps.accounts.models import OidcBrowserAttempt

    row = OidcBrowserAttempt.objects.create(
        provider="github", state_digest="s" * 64, nonce_digest="n" * 64, code_verifier="v", redirect_uri="https://a/cb",
        origin="https://a", expires_at="2099-01-01T00:00:00Z", next_path="/loans")
    assert OidcBrowserAttempt.objects.get(pk=row.pk).next_path == "/loans"
