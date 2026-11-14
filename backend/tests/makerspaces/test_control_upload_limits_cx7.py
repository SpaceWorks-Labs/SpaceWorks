"""The direct admin uploads share API limits, accounting, and failure behavior."""
import pytest
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import RequestFactory
from unfold.admin import ModelAdmin

from apps.evidence.storage import StorageUnavailable
from apps.inventory import public_image_storage
from apps.inventory.admin_image_uploads import PublicImageAdminForm
from apps.inventory.models import InventoryProduct
from apps.makerspaces.admin_images import MakerspaceAdminForm, MakerspaceImageAdminMixin
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form, form_errors
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


class ProductImageForm(PublicImageAdminForm):
    class Meta:
        model = InventoryProduct
        fields = ("name",)


class SpaceImageForm(MakerspaceAdminForm):
    class Meta:
        model = MakerspaceAdminForm.Meta.model
        fields = ("name", "slug")


def upload(size):
    return SimpleUploadedFile("photo.png", b"x" * size, content_type="image/png")


def image_form(space, surface, size):
    if surface == "product":
        row, _ = InventoryProduct.objects.get_or_create(makerspace=space, name="Image owner")
        return ProductImageForm(data={"name": row.name}, files={"image_upload": upload(size)}, instance=row)
    return SpaceImageForm(data={"name": space.name, "slug": space.slug},
                          files={"logo_upload": upload(size)}, instance=space)


@pytest.mark.parametrize("surface", ["product", "space"])
@pytest.mark.parametrize("key,code", [("upload_bytes", "upload_limit"), ("storage", "upload_limit"),
                                     ("storage_public_images_bytes", "storage_public_images_bytes_quota_reached")])
def test_image_form_accepts_max_refuses_one_more_with_api_error(surface, key, code, settings):
    settings.PUBLIC_IMAGE_MAX_BYTES = 4096
    space = make_space("cx7-control-image-limit")
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    with transaction.atomic():
        maximum = image_form(space, surface, 10)
        assert maximum.is_valid(), maximum.errors
    refused = image_form(space, surface, 11)
    assert refused.is_valid() is False
    assert [item[0] for item in form_errors(refused)] == [code]
    space.refresh_from_db()
    assert space.storage_bytes_used == 0


@pytest.mark.parametrize("key,code", [("storage", "limit_reached"),
                                     ("storage_public_images_bytes", "storage_public_images_bytes_quota_reached")])
def test_logo_and_cover_share_storage_but_each_has_its_own_file_cap(key, code, settings):
    settings.PUBLIC_IMAGE_MAX_BYTES = 4096
    space = make_space("cx7-control-two-images")
    space.resource_limit_overrides = {key: 20, "upload_bytes": 10}
    space.save(update_fields=["resource_limit_overrides"])
    def form():
        return SpaceImageForm(data={"name": space.name, "slug": space.slug},
                              files={"logo_upload": upload(10), "cover_upload": upload(10)}, instance=space)
    maximum = form()
    assert maximum.is_valid(), maximum.errors
    space.resource_limit_overrides[key] = 19
    space.save(update_fields=["resource_limit_overrides"])
    refused = form()
    assert refused.is_valid() is False
    assert [item[0] for item in form_errors(refused)] == [code]


@pytest.mark.parametrize("failure", [False, True])
def test_inventory_image_save_charges_success_and_rolls_back_failed_storage(failure, monkeypatch):
    space = make_space("cx7-control-image-charge")
    space.resource_limit_overrides = {"storage": 10, "upload_bytes": 10, "storage_public_images_bytes": 10}
    space.save(update_fields=["resource_limit_overrides"])
    row = InventoryProduct.objects.create(makerspace=space, name="Image owner")
    actor = superadmin("cx7-image-root")
    form, model_admin, request, data = bound_form(row, actor, instance=row)
    form = type(form)(data=data, files={"image_upload": upload(10)}, instance=row)
    writes = []
    def put(key, data, content_type):
        if failure:
            raise StorageUnavailable
        writes.append((key, data, content_type))
    monkeypatch.setattr(public_image_storage, "put_bytes", put)
    with transaction.atomic():
        assert form.is_valid(), form.errors
        model_admin.save_model(request, form.save(commit=False), form, True)
    space.refresh_from_db()
    row.refresh_from_db()
    assert space.storage_bytes_used == (0 if failure else 10)
    assert bool(row.image_key) is (not failure)
    assert len(writes) == (0 if failure else 1)


def test_space_model_save_preserves_the_new_storage_charge(monkeypatch):
    space = make_space("cx7-control-space-image-charge")
    space.resource_limit_overrides = {"storage": 20, "upload_bytes": 10}
    space.save(update_fields=["resource_limit_overrides"])
    monkeypatch.setattr(public_image_storage, "put_bytes", lambda *args: None)
    form = SpaceImageForm(data={"name": space.name, "slug": space.slug},
                          files={"logo_upload": upload(10), "cover_upload": upload(10)}, instance=space)
    # Exercise the production image mixin and Django's actual ModelAdmin.save_model.
    class ImageAdmin(MakerspaceImageAdminMixin, ModelAdmin):
        pass
    model_admin = ImageAdmin(type(space), admin.site)
    request = RequestFactory().post("/control/")
    request.user = superadmin("cx7-space-image-root")
    with transaction.atomic():
        assert form.is_valid(), form.errors
        model_admin.save_model(request, form.save(commit=False), form, True)
    space.refresh_from_db()
    assert space.storage_bytes_used == 20
    assert space.logo_key != ""
    assert space.cover_image_key != ""


def test_replaced_image_releases_its_original_tenant_only(monkeypatch, django_capture_on_commit_callbacks):
    source = make_space("cx7-image-source")
    target = make_space("cx7-image-target")
    source.storage_bytes_used = 5
    source.save(update_fields=["storage_bytes_used"])
    target.resource_limit_overrides = {"storage": 10}
    target.save(update_fields=["resource_limit_overrides"])
    row = InventoryProduct.objects.create(makerspace=source, name="Moved image", image_key="items/source/old.png")
    actor = superadmin("cx7-image-move-root")
    form, model_admin, request, data = bound_form(row, actor, instance=row)
    data["makerspace"] = target.pk
    form = type(form)(data=data, files={"image_upload": upload(10)}, instance=row)
    monkeypatch.setattr(public_image_storage, "put_bytes", lambda *args: None)
    monkeypatch.setattr(public_image_storage, "object_size", lambda key: 5)
    monkeypatch.setattr(public_image_storage, "delete_object", lambda key: True)
    with django_capture_on_commit_callbacks(execute=True), transaction.atomic():
        assert form.is_valid(), form.errors
        model_admin.save_model(request, form.save(commit=False), form, True)
    source.refresh_from_db()
    target.refresh_from_db()
    row.refresh_from_db()
    assert source.storage_bytes_used == 0
    assert target.storage_bytes_used == 10
    assert row.makerspace_id == target.pk
