"""#208: a Shop product's public image reuses the validated public-image pipeline (local, untracked)."""

from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.shop.models import ShopProduct

from .helpers import client, manager, product, shop_space, staff

pytestmark = pytest.mark.django_db


def _mock_storage(monkeypatch, size=123):
    from apps.inventory import public_image_storage as pis

    monkeypatch.setattr(pis, "presigned_upload", lambda key, ct: {"url": "http://minio/up", "fields": {"key": key}})
    monkeypatch.setattr(pis, "finalize_upload", lambda key: pis._finalize_result(key, size))
    monkeypatch.setattr(pis, "sniff_is_valid_image", lambda key: True)
    delete = Mock()
    monkeypatch.setattr(pis, "delete_object", delete)
    return delete


def _url(row):
    return f"/api/v1/admin/shop/products/{row.pk}/image/"


def test_shop_manager_uploads_replaces_and_clears_a_product_image_with_audit(
        monkeypatch, settings, django_capture_on_commit_callbacks):
    settings.PUBLIC_IMAGE_BASE_URL = "http://cdn.test/public-images"
    delete = _mock_storage(monkeypatch)
    space = shop_space("img-a", "shop.online")
    sm = manager(space)
    row, _variant = product(space, sm)
    api = client(staff(space, "shop_manager"))

    presigned = api.post(_url(row), {"content_type": "image/png", "filename": "p.png"}, format="json")
    assert presigned.status_code == 201, presigned.content
    key = presigned.data["object_key"]
    assert key.startswith(f"shop/{space.pk}/")
    attached = api.put(_url(row), {"object_key": key}, format="json")
    assert attached.status_code == 200, attached.content
    assert attached.data["image_url"] == f"http://cdn.test/public-images/{key}"
    assert "image_key" not in attached.data
    row.refresh_from_db()
    assert row.image_key == key
    listed = client().get(f"/api/v1/public/m/{space.slug}/shop/products/")
    assert listed.status_code == 200, listed.content
    body = listed.json()
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    assert any(item.get("image_url") == f"http://cdn.test/public-images/{key}" for item in rows)

    with django_capture_on_commit_callbacks(execute=True):
        cleared = api.delete(_url(row))
    assert cleared.status_code == 200
    assert not cleared.data["image_url"]
    row.refresh_from_db()
    assert row.image_key == ""
    delete.assert_called_once_with(key)
    actions = set(AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))
    assert {"shop.product_image_set", "shop.product_image_cleared"} <= actions


def test_a_key_outside_this_shop_or_already_used_is_refused(monkeypatch):
    _mock_storage(monkeypatch)
    space = shop_space("img-b")
    sm = manager(space)
    (row, _v1), (other, _v2) = product(space, sm), product(space, sm, name="Other")
    ShopProduct.objects.filter(pk=other.pk).update(image_key=f"shop/{space.pk}/taken.png")
    api = client(sm)
    assert api.put(_url(row), {"object_key": "shop/999999/x.png"}, format="json").status_code == 400
    assert api.put(_url(row), {"object_key": f"shop/{space.pk}/taken.png"}, format="json").status_code == 400
    row.refresh_from_db()
    assert row.image_key == ""


def test_other_tenants_and_non_shop_staff_cannot_manage_product_images(monkeypatch):
    _mock_storage(monkeypatch)
    space, other_space = shop_space("img-c"), shop_space("img-d")
    row, _variant = product(space, manager(space))
    body = {"content_type": "image/png", "filename": "p.png"}
    assert client(manager(other_space)).post(_url(row), body, format="json").status_code == 404
    assert client(staff(space, "booking_manager")).post(_url(row), body, format="json").status_code in (403, 404)
    assert AuditLog.objects.filter(action__startswith="shop.product_image").count() == 0
