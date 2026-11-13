"""Every public projection must lose private/unreleased content immediately."""

import pytest
from django.http import HttpResponse

from apps.bookings.models_website import BookingResourcePageSection
from apps.bookings.services_website import set_release
from apps.bookings.services_website_assets import upload_asset
from tests.bookings.website_helpers import world, image, memory_storage

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("public,active,feature,released", [
    (p, a, f, r) for p in (False, True) for a in (False, True)
    for f in (False, True) for r in (False, True)
])
def test_full_public_projection_matrix(monkeypatch, public, active, feature, released):
    w = world()
    memory_storage(monkeypatch)
    asset = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Gallery")
    page = w.resource.website_page
    page.sections.update(asset=asset)
    page.released = released
    page.save()
    w.resource.is_public, w.resource.is_active = public, active
    w.resource.save()
    if not feature:
        w.tenant.enabled_features.remove("bookings.website")
        w.tenant.save()
    monkeypatch.setattr("apps.bookings.views_website_public.image_response", lambda row: HttpResponse(b"webp"))
    core = w.public.get(w.base)
    assert core.status_code == (200 if public and active else 404)
    visible = public and active and feature and released
    for url in [w.base + "website/", w.base + f"website/assets/{asset.pk}/", w.embed, w.share]:
        assert w.public.get(url).status_code == (200 if visible else 404), url
    if core.status_code == 200:
        assert bool(core.data["website"]) == visible
        assert {"member", "email", "note", "buffer_before_minutes", "machine_type"}.isdisjoint(core.data)
    directory = w.public.get("/api/v1/discover/bookings/")
    assert directory.data["count"] == int(public and active)
    assert "Public guidance" not in str(directory.data)


def test_private_assets_are_never_served_by_id_or_foreign_page(monkeypatch):
    w = world()
    memory_storage(monkeypatch)
    asset = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Draft")
    page = w.resource.website_page
    page.sections.update(visibility="draft", asset=asset)
    image_url = w.base + f"website/assets/{asset.pk}/"
    assert w.public.get(image_url).status_code == 404
    other = world(slug="other")
    assert other.public.get(other.base + f"website/assets/{asset.pk}/").status_code == 404
    monkeypatch.setattr("apps.bookings.services_website_assets.private_image_response", lambda key: HttpResponse(b"webp"))
    assert w.staff.get(w.admin + f"assets/{asset.pk}/").status_code == 200


@pytest.mark.parametrize("change", ["module", "archive", "inactive"])
def test_live_visibility_drops_previously_served_share_and_sitemap(change):
    w = world()
    assert w.public.get(w.share).status_code == 200  # warm shared cache
    if change == "module":
        w.tenant.enabled_modules.remove("bookings")
    elif change == "archive":
        from django.utils import timezone
        w.tenant.archived_at = timezone.now()
    else:
        w.resource.is_active = False
        w.resource.save()
    w.tenant.save()
    assert w.public.get(w.share).status_code == 404
    assert w.public.get(w.embed).status_code == 404
    assert w.public.get(w.base).status_code == 404


def test_uniform_unknown_foreign_and_private_detail():
    w = world()
    from uuid import uuid4
    assert w.public.get(w.base.replace(str(w.resource.public_token), str(uuid4()))).status_code == 404
    assert w.public.get(w.base.replace(w.tenant.slug, "missing")).status_code == 404
    w.resource.is_public = False
    w.resource.save()
    assert w.public.get(w.base).status_code == 404


def test_unrelease_invalidates_share_content_immediately():
    w = world()
    assert w.public.get(w.share).status_code == 200
    w.resource.website_page.refresh_from_db()
    set_release(w.resource, actor=w.actor, data={"released": False, "revision": w.resource.website_page.revision})
    assert w.public.get(w.share).status_code == 404
    assert w.public.get(w.base).data["website"] is None
