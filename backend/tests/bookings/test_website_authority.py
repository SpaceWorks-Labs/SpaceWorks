import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.bookings.models_website import BookingResourcePage, BookingResourcePageSection, BookingResourcePageAsset
from apps.bookings.services_website import save_content, set_release
from tests.bookings.website_helpers import world, section

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("permission,save,release,preview", [
    ("edit_details", 200, 403, 200), ("publish_page", 403, 200, 200),
    ("manage_reservations", 403, 403, 403), ("check_in", 403, 403, 403),
])
def test_resource_permission_operation_matrix(permission, save, release, preview):
    w = world(permission)
    page = w.resource.website_page
    assert w.staff.get(w.admin).status_code == preview
    assert w.staff.put(w.admin, {"revision": page.revision, "sections": [section()]}, format="json").status_code == save
    page.refresh_from_db()
    assert w.staff.post(w.admin + "release/", {"released": False, "revision": page.revision}, format="json").status_code == release


def test_revocation_and_foreign_resource_deny_without_side_effects():
    w = world()
    other = world(slug="foreign")
    assert w.staff.get(other.admin).status_code in (403, 404)
    from django.utils import timezone
    w.grant.revoked_at = timezone.now()
    w.grant.save()
    before = AuditLog.objects.count()
    assert w.staff.put(w.admin, {"revision": 3, "sections": [section()]}, format="json").status_code in (403, 404)
    assert AuditLog.objects.count() == before


def test_revision_unknown_fields_bounds_and_foreign_asset_are_atomic():
    w = world()
    page = w.resource.website_page
    page.refresh_from_db()
    revision = page.revision
    for payload in [
        {"revision": 0, "sections": []}, {"revision": revision, "released": True, "sections": []},
        {"revision": revision, "sections": [section(url="javascript:alert(1)")]},
        {"revision": revision, "sections": [section(body="x" * 10001)]},
        {"revision": revision, "sections": [section(), section()]},
        {"revision": revision, "sections": [section(asset_id=999999)]},
        {"revision": revision, "sections": [section(note="secret")]},
    ]:
        with pytest.raises(ValidationError):
            save_content(w.resource, actor=w.actor, data=payload)
        page.refresh_from_db()
        assert page.revision == revision and page.sections.get().body == "Public guidance"
    with pytest.raises(ValidationError):
        set_release(w.resource, actor=w.actor, data={"revision": 0, "released": True})


def test_editor_cannot_change_public_policy_or_release_private_resource():
    w = world("publish_page")
    w.resource.is_public = False
    w.resource.save()
    page = w.resource.website_page
    page.refresh_from_db()
    with pytest.raises(ValidationError):
        set_release(w.resource, actor=w.grantee, data={"revision": page.revision, "released": True})
    w.resource.refresh_from_db()
    assert not w.resource.is_public


def test_database_rejects_cross_page_assets_and_reparenting():
    w, other = world(), world(slug="foreign")
    p, q = w.resource.website_page, other.resource.website_page
    asset = BookingResourcePageAsset.objects.create(page=q, object_key="foreign", size_bytes=1, alt_text="Foreign")
    with pytest.raises(IntegrityError), transaction.atomic():
        p.sections.update(asset=asset)
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingResourcePage.objects.filter(pk=p.pk).update(space=other.resource)
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingResourcePageAsset.objects.filter(pk=asset.pk).update(page=p)


def test_every_write_audits_only_revision():
    w = world()
    save_content(w.resource, actor=w.actor, data={"revision": 3, "sections": [section(body="Publication text")]})
    rows = AuditLog.objects.filter(makerspace=w.tenant, action__startswith="booking.website_")
    assert rows.count() == 3
    assert all(set(row.meta) == {"revision"} for row in rows)


@pytest.mark.parametrize("permission,expected", [
    ("edit_details", 201), ("publish_page", 403), ("manage_reservations", 403), ("check_in", 403),
])
def test_asset_mutations_need_edit_details(monkeypatch, permission, expected):
    from tests.bookings.website_helpers import memory_storage, image
    w = world(permission)
    memory_storage(monkeypatch)
    response = w.staff.post(w.admin + "assets/", {"file": image(), "alt_text": "Image"}, format="multipart")
    assert response.status_code == expected
    if expected == 201:
        asset_url = w.admin + f"assets/{response.data['id']}/"
        assert w.staff.delete(asset_url).status_code == 204


def test_wrong_origin_and_inactive_editor_cannot_save():
    w = world()
    # Origin scoping binds a browser origin to the tenant that verified it; an origin
    # no tenant claims is unscoped, so the foreign origin must belong to another tenant.
    foreign = world(slug="foreign-origin").tenant
    foreign.frontend_domain = "foreign.example.test"
    foreign.frontend_domain_status = "verified"
    foreign.save(update_fields=["frontend_domain", "frontend_domain_status"])
    payload = {"revision": 3, "sections": []}
    assert w.staff.put(w.admin, payload, format="json", HTTP_ORIGIN="https://foreign.example.test").status_code == 403
    w.grantee.is_active = False
    w.grantee.save(update_fields=["is_active"])
    assert w.staff.put(w.admin, payload, format="json").status_code == 403
