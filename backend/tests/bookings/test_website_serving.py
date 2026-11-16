from pathlib import Path

import pytest
from django.conf import settings
from apps.bookings.models import BookableSpace
from apps.makerspaces.models import Makerspace
from tests.bookings.website_helpers import world

pytestmark = pytest.mark.django_db(transaction=True)


def test_embed_exact_origins_framing_and_share_escaping():
    w = world()
    response = w.public.get(w.embed)
    assert response.status_code == 200
    assert "https://display.example.test" in response["Content-Security-Policy"]
    assert "X-Frame-Options" not in response
    assert response["Referrer-Policy"] == "no-referrer"
    for origins in ([], ["https://*.example.test"], ["https://display.example.test/path"], ["http://display.example.test"]):
        w.tenant.website_embed_origins = origins
        w.tenant.save()
        assert w.public.get(w.embed).status_code == 404
    w.resource.name = '<script>alert("x")</script>'
    w.resource.save()
    response = w.public.get(w.share)
    assert b"<script>" not in response.content and b"&lt;script&gt;" in response.content
    assert response["X-Robots-Tag"] == "noindex"


def test_discovery_pagination_consent_and_list_array_compatibility():
    w = world()
    for i in range(26):
        BookableSpace.objects.create(makerspace=w.tenant, name=f"Room {i:02}", is_public=True)
    response = w.public.get("/api/v1/discover/bookings/")
    assert response.status_code == 200 and response.data["count"] == 27
    assert len(response.data["results"]) == 24
    assert len(w.public.get("/api/v1/discover/bookings/?page=2").data["results"]) == 3
    w.resource.location, w.resource.kind = "North lab", "bench"
    w.resource.save()
    filtered = w.public.get("/api/v1/discover/bookings/?kind=bench&location=north&q=lab")
    assert filtered.data["count"] == 1 and filtered.data["results"][0]["title"] == w.resource.name
    assert w.public.get("/api/v1/discover/bookings/?date_from=2030-01-01").status_code == 400
    assert isinstance(w.public.get(f"/api/v1/public/{w.tenant.slug}/spaces/").data, list)
    w.tenant.frontend_domain = "booking-directory.example.test"
    w.tenant.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
    w.tenant.hidden_from_central_directory = True
    w.tenant.save()
    assert w.public.get("/api/v1/discover/bookings/").data["count"] == 0
    assert w.public.get(w.base).status_code == 200


def test_custom_domain_sitemap_and_canonical_share_url(settings):
    w = world()
    w.tenant.frontend_domain = "booking.example.test"
    w.tenant.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
    w.tenant.save()
    settings.ALLOWED_HOSTS = ["booking.example.test", "testserver", "evil.example.test"]
    response = w.public.get("/sitemap.xml", HTTP_HOST="booking.example.test")
    url = f"https://booking.example.test/bookings/{w.resource.public_token}"
    assert response.status_code == 200 and url.encode() in response.content
    assert url.encode() in w.public.get(w.share).content
    assert w.public.get("/sitemap.xml", HTTP_HOST="evil.example.test").status_code == 404


def test_serving_configs_keep_spa_framing_protection_through_fallback():
    root = Path(__file__).resolve().parents[3]
    nginx = (root / "frontend/nginx.conf").read_text()
    assert 'location = /index.html' in nginx
    # Framing headers come from the runtime include that every SPA/static location
    # pulls in (a location-level add_header drops inherited server-level headers).
    assert 'add_header X-Frame-Options' not in nginx
    assert nginx.count('include /etc/nginx/analytics-headers.conf;') >= 6
    headers = (root / "frontend/docker-entrypoint.d/40-web-analytics.sh").read_text()
    defaults = headers[:headers.index('if [ -n "$script$collect$domain" ]')]
    assert 'X-Frame-Options "DENY"' in defaults and "frame-ancestors 'none'" in defaults
    assert '/share/bookings/$booking_share_token/' in nginx
    for name in ("Caddyfile", "Caddyfile.saas", "Caddyfile.saas-install"):
        body = (root / "deploy" / name).read_text()
        assert '/share/bookings/' in body and 'frame-ancestors' in body and '/embed/*' in body


def test_public_availability_and_name_flags_are_unchanged(monkeypatch):
    from tests.bookings.test_staff_tools_helpers import world as booking_world
    from datetime import timedelta
    w = booking_world(monkeypatch)
    w.resource.is_public = True
    w.resource.show_public_availability = False
    w.resource.show_public_booker_names = False
    w.resource.save()
    from rest_framework.test import APIClient
    client = APIClient()
    url = f"/api/v1/public/{w.tenant.slug}/spaces/{w.resource.public_token}/availability/"
    query = {"starts_at": w.row.starts_at.isoformat(), "ends_at": (w.row.ends_at + timedelta(hours=1)).isoformat()}
    assert client.get(url, query).data["availability"] is None
    w.resource.show_public_availability = True
    w.resource.save()
    assert client.get(url, query).data["availability"][0]["booker_name"] is None
    w.resource.show_public_booker_names = True
    w.resource.save()
    assert client.get(url, query).data["availability"][0]["booker_name"] == w.row.name


def test_public_endpoints_are_throttled(monkeypatch):
    from apps.apiclients.throttling import ClientTierRateThrottle
    w = world()
    monkeypatch.setattr(ClientTierRateThrottle, "allow_request", lambda *args: False)
    monkeypatch.setattr(ClientTierRateThrottle, "wait", lambda *args: 1)
    for url in (w.base, w.base + "website/", w.base + "website/assets/1/", w.embed, w.share,
                "/api/v1/discover/bookings/", "/sitemap.xml"):
        assert w.public.get(url).status_code == 429
