"""L25: Metabase signed embedding (HS256, one dashboard, ten-minute expiry), the embed route,
and the SCRAM verifier the app computes so the clear password never reaches the server."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest

from apps.analytics import embedding, provisioning
from apps.audit.models import AuditLog

from .helpers import SECRET, client_for, manager, platform_url, space, space_url, superadmin


def _decode(part):
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def test_the_token_is_hs256_signed_for_one_dashboard_and_expires_in_ten_minutes():
    url, expires_at = embedding.dashboard_url("https://mb.example.org/", SECRET, 12, now=1_800_000_000)
    assert url.startswith("https://mb.example.org/embed/dashboard/") and url.endswith("#bordered=true&titled=true")
    token = url.split("/embed/dashboard/")[1].split("#")[0]
    header, body, signature = token.split(".")
    assert _decode(header) == {"alg": "HS256", "typ": "JWT"}
    assert _decode(body) == {"exp": 1_800_000_600, "params": {}, "resource": {"dashboard": 12}}
    expected = hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)) == expected
    assert expires_at == datetime.fromtimestamp(1_800_000_600, tz=UTC)
    assert embedding.EMBED_TTL_SECONDS == 600


def test_a_wrong_secret_does_not_verify():
    url, _ = embedding.dashboard_url("https://mb.example.org", SECRET, 1, now=1)
    header, body, signature = url.split("/embed/dashboard/")[1].split("#")[0].split(".")
    other = hmac.new(b"x" * 64, f"{header}.{body}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)) != other


@pytest.mark.parametrize("value", ["javascript:alert(1)", "https://u:p@mb.example.org", "https://mb.example.org#x",
                                   "mb.example.org", "file:///etc/passwd"])
def test_site_urls_are_validated(value):
    with pytest.raises(embedding.EmbedUrlInvalid):
        embedding.normalize_site_url(value)


@pytest.mark.django_db
def test_the_embed_route_signs_only_listed_dashboards_audits_and_hides_the_secret():
    makerspace = space()
    client = client_for(manager(makerspace))
    not_configured = client.get(space_url("-embed", makerspace, 4))
    assert (not_configured.status_code, not_configured.data["code"]) == (409, "analytics_not_configured")
    client.patch(space_url("-connection", makerspace), {
        "metabase_url": "https://mb.example.org", "embed_secret": SECRET, "dashboards": [{"id": 4, "title": "Loans"}],
    }, format="json")
    response = client.get(space_url("-embed", makerspace, 4))
    assert response.status_code == 200
    assert SECRET not in json.dumps(response.data, default=str)
    assert response["Cache-Control"] == "no-store"
    unlisted = client.get(space_url("-embed", makerspace, 5))
    assert (unlisted.status_code, unlisted.data["code"]) == (409, "analytics_dashboard_unknown")
    viewed = AuditLog.objects.filter(action="analytics.dashboard_viewed", makerspace=makerspace).get()
    assert viewed.meta["dashboard"] == 4 and SECRET not in json.dumps(viewed.meta)


@pytest.mark.django_db
def test_the_platform_embed_is_superadmin_only_and_platform_scoped():
    client = client_for(superadmin())
    client.patch(platform_url("-connection"), {
        "metabase_url": "https://mb.example.org", "embed_secret": SECRET, "dashboards": [{"id": 9, "title": "All"}],
    }, format="json")
    assert client.get(platform_url("-embed", 9)).status_code == 200
    assert AuditLog.objects.filter(action="analytics.dashboard_viewed", makerspace__isnull=True).exists()


def test_the_scram_verifier_has_postgres_format_and_matches_rfc_5802():
    salt = b"0123456789abcdef"
    verifier = provisioning.scram_verifier("pencil", salt=salt, iterations=4096)
    prefix, keys = verifier.split("$", 1)[1].split("$")
    iterations, b64salt = prefix.split(":")
    stored, server = keys.split(":")
    assert verifier.startswith("SCRAM-SHA-256$4096:") and base64.b64decode(b64salt) == salt
    salted = hashlib.pbkdf2_hmac("sha256", b"pencil", salt, 4096)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    assert base64.b64decode(stored) == hashlib.sha256(client_key).digest()
    assert base64.b64decode(server) == hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    assert "pencil" not in verifier
