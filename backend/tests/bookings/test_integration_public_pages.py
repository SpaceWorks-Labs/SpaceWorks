"""Signed page reads retain the independent BK-F publication boundary."""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.apiclients.scope_registry_routes import SCOPE_REGISTRY, PUBLIC_READ_SCOPES, TARGET_TENANT_SLUG
from apps.bookings.models import BookableSpace
from apps.bookings.models_website import BookingResourcePage, BookingResourcePageAsset, BookingResourcePageSection
from tests.bookings.integration_read_helpers import PREFIX, read_world, signed

pytestmark = pytest.mark.django_db


@pytest.fixture
def published_world(read_world):
    w = read_world
    w.tenant.enabled_features = [*w.tenant.enabled_features, "bookings.website"]
    w.tenant.save(update_fields=["enabled_features"])
    w.resource.is_public = True
    w.resource.payment_amount = Decimal("12.50")
    w.resource.save(update_fields=["is_public", "payment_amount"])
    w.page = BookingResourcePage.objects.create(space=w.resource, released=True)
    w.asset = BookingResourcePageAsset.objects.create(page=w.page, object_key="private/booking/published.webp",
                                                     size_bytes=100, alt_text="Public image")
    w.draft_asset = BookingResourcePageAsset.objects.create(page=w.page, object_key="private/booking/draft.webp",
                                                           size_bytes=100, alt_text="Private image")
    for position, kind in enumerate(BookingResourcePageSection.Kind.values):
        BookingResourcePageSection.objects.create(page=w.page, kind=kind, slug=kind, title=kind,
            body=f"Published {kind}", visibility="published", position=position,
            asset=w.asset if kind == "gallery" else None,
            url="https://example.test/" if kind in {"link", "sponsor"} else "")
    BookingResourcePageSection.objects.create(page=w.page, kind="gallery", slug="private-gallery",
        title="Private draft", body="Unreleased secret", visibility="draft", asset=w.draft_asset)
    return w


def resource_data(w, surface):
    suffix = "resources/" if surface == "list" else f"resources/{w.resource.pk}/"
    response = signed(w.client, PREFIX + suffix)
    assert response.status_code == 200
    return response.json()["results"][0] if surface == "list" else response.json()


@pytest.mark.parametrize("surface", ["list", "detail"])
def test_signed_resource_uses_released_public_allow_list(published_world, surface):
    w = published_world
    page = resource_data(w, surface)["public_page"]
    assert set(page) == {"public_url", "embed_path", "payment_amount", "currency", "rules", "sections"}
    assert page["payment_amount"] == "12.50"
    assert set(page["rules"]) == {"minimum_minutes", "maximum_minutes", "lead_minutes", "advance_days", "cancellation_cutoff_hours"}
    assert [section["kind"] for section in page["sections"]] == list(BookingResourcePageSection.Kind.values)
    for section in page["sections"]:
        assert set(section) == {"kind", "slug", "title", "body", "url", "position", "image_url", "image_alt_text"}
    gallery = page["sections"][-1]
    assert gallery["image_url"] == f"/api/v1/public/{w.tenant.slug}/spaces/{w.resource.public_token}/website/assets/{w.asset.pk}/"
    serialized = str(page)
    for secret in [w.asset.object_key, w.draft_asset.object_key, "Private draft", "Unreleased secret", "asset_id"]:
        assert secret not in serialized


@pytest.mark.parametrize("surface", ["list", "detail"])
@pytest.mark.parametrize("gate", ["private", "inactive", "missing", "unreleased", "website_off", "edition"])
def test_signed_authority_does_not_bypass_publication(published_world, surface, gate, settings):
    w = published_world
    if gate in {"private", "inactive"}:
        BookableSpace.objects.filter(pk=w.resource.pk).update(**{"is_public" if gate == "private" else "is_active": False})
    elif gate == "missing":
        w.page.delete()
    elif gate == "unreleased":
        w.page.released = False
        w.page.save(update_fields=["released"])
    elif gate == "website_off":
        w.tenant.enabled_features.remove("bookings.website")
        w.tenant.save(update_fields=["enabled_features"])
    else:
        settings.SPACEWORKS_EDITION = "events"
    assert resource_data(w, surface)["public_page"] is None


@pytest.mark.parametrize("gate", ["module", "archived", "importing", "aborted"])
def test_published_resource_still_requires_live_tenant(published_world, gate):
    from django.utils import timezone
    w = published_world
    if gate == "module":
        w.tenant.enabled_modules = [key for key in w.tenant.enabled_modules if key != "bookings"]
    elif gate == "archived":
        w.tenant.archived_at = timezone.now()
    else:
        w.tenant.lifecycle_state = w.tenant.LifecycleState(gate)
    w.tenant.save()
    for suffix in ["resources/", f"resources/{w.resource.pk}/"]:
        assert signed(w.client, PREFIX + suffix).status_code in {401, 404}


def test_public_image_endpoint_refuses_draft_and_revoked_publication(published_world):
    w = published_world
    base = f"/api/v1/public/{w.tenant.slug}/spaces/{w.resource.public_token}/website/assets/"
    assert APIClient().get(base + f"{w.draft_asset.pk}/").status_code == 404
    w.page.released = False
    w.page.save(update_fields=["released"])
    assert APIClient().get(base + f"{w.asset.pk}/").status_code == 404


def test_booking_public_routes_do_not_receive_server_scopes():
    # Discovery is mounted outside the HMAC-protected prefixes, so it has no entry.
    assert not any(name == "website-discover" for name, _method in SCOPE_REGISTRY)
    for name in ["public-booking-resource", "public-booking-website", "public-booking-website-image"]:
        for method in ["GET", "HEAD"]:
            entry = SCOPE_REGISTRY[(name, method)]
            # Public scopes only (a per-domain `public:bookings:read` rides along); never a server scope.
            assert entry.scopes >= PUBLIC_READ_SCOPES and all(scope.startswith("public:") for scope in entry.scopes)
            assert not entry.server_only and not entry.legacy_v1
            assert entry.target_mode == TARGET_TENANT_SLUG
