"""Real booking-only authority, website and private storage fixtures."""

from io import BytesIO
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings.services_website import save_content, set_release
from apps.makerspaces import website_assets
from tests.bookings.staff_grant_helpers import grant_fixture, client_for


def section(**values):
    return {"kind": "faq", "slug": "faq", "title": "Questions", "body": "Public guidance",
            "url": "", "asset_id": None, "visibility": "published", "position": 0, **values}


def world(permission="edit_details", slug="website"):
    tenant, actor, grantee, resource, grant, member = grant_fixture(permission, slug=slug)
    tenant.enabled_features += ["bookings.website", "bookings.embed", "bookings.clone"]
    tenant.public_site_enabled = True
    tenant.hidden_from_central_directory = False
    tenant.website_embed_origins = ["https://display.example.test"]
    tenant.save()
    resource.is_public = True
    resource.save()
    save_content(resource, actor=actor, data={"revision": 0, "sections": [section()]})
    page = resource.website_page
    set_release(resource, actor=actor, data={"revision": page.revision, "released": True})
    page.refresh_from_db()
    return SimpleNamespace(tenant=tenant, actor=actor, grantee=grantee, member=member,
        resource=resource, grant=grant, staff=client_for(grantee), public=APIClient(),
        admin=f"/api/v1/admin/spaces/{resource.pk}/website/",
        base=f"/api/v1/public/{tenant.slug}/spaces/{resource.public_token}/",
        embed=f"/embed/{tenant.slug}/bookings/{resource.public_token}/",
        share=f"/share/bookings/{resource.public_token}/")


def image():
    output = BytesIO()
    Image.new("RGB", (20, 20), "red").save(output, format="PNG")
    return SimpleUploadedFile("photo.png", output.getvalue(), content_type="image/png")


def memory_storage(monkeypatch):
    objects, deleted = {}, []
    monkeypatch.setattr(website_assets.limits, "is_self_host", lambda: False)
    monkeypatch.setattr(website_assets.limits, "resource_limit", lambda *args: 100_000_000)
    monkeypatch.setattr(website_assets, "_put", lambda key, data, mime: objects.__setitem__(key, data))
    monkeypatch.setattr(website_assets, "object_size", lambda key: len(objects[key]) if key in objects else None)
    def delete(key):
        deleted.append(key)
        objects.pop(key, None)
        return True
    monkeypatch.setattr(website_assets, "delete_object", delete)
    monkeypatch.setattr(website_assets, "copy_object", lambda source, target: objects.__setitem__(target, objects[source]))
    return objects, deleted
