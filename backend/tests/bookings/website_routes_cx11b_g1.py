"""Every website method, with real editorial revisions and re-encoded image bytes."""
from io import BytesIO
from types import SimpleNamespace

from apps.bookings.models_website import BookingResourcePage, BookingResourcePageAsset, BookingResourcePageSection
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields
from tests.bookings.website_helpers import image, memory_storage, section

KEYS = ("bookings", "bookings.website")
ROUTES = (
    Route("admin-booking-website", keys=KEYS),
    Route("admin-booking-website", "PUT", KEYS, audit=("booking.website_saved",)),
    Route("admin-booking-website-release", "POST", KEYS, audit=("booking.website_released",)),
    Route("admin-booking-website-assets", "POST", KEYS, 201, ("booking.website_asset_saved",)),
    Route("admin-booking-website-asset", keys=KEYS),
    Route("admin-booking-website-asset", "DELETE", KEYS, 204, ("booking.website_asset_removed",)),
    Route("public-booking-resource", keys=KEYS, standing="public"),
    Route("public-booking-website", keys=KEYS, feature_code="not_found", standing="public"),
    Route("public-booking-website-image", keys=KEYS, feature_code="not_found", standing="public"),
)


def setup(w, monkeypatch):
    from apps.evidence import storage as private_storage
    from apps.makerspaces import website_assets
    w.tenant.public_site_enabled = True
    w.tenant.hidden_from_central_directory = False
    w.tenant.save(update_fields=["public_site_enabled", "hidden_from_central_directory"])
    objects, deleted = memory_storage(monkeypatch)
    page = BookingResourcePage.objects.create(space=w.room, released=True, revision=3)
    key = website_assets.prefix("bookings", w.tenant.pk, page.pk) + "seed.webp"
    payload = website_assets.webp(image().read())
    objects[key] = payload
    asset = BookingResourcePageAsset.objects.create(page=page, object_key=key, size_bytes=len(payload), alt_text="Retained studio image")
    BookingResourcePageSection.objects.create(page=page, asset=asset, **{k: v for k, v in section(title="Retained studio FAQ").items() if k != "asset_id"})
    monkeypatch.setattr(private_storage, "object_size", lambda k: len(objects[k]) if k in objects else None)
    monkeypatch.setattr(private_storage, "_client", lambda: SimpleNamespace(get_object=lambda **kw: {"Body": BytesIO(objects[kw["Key"]])}))
    name, method = w.route.name, w.route.method
    if name == "admin-booking-website" and method == "PUT":
        w.body = {"revision": 3, "sections": [section(title="Changed studio FAQ Δ")]}
        def saved(r):
            fields(page, revision=4, released=True)
            equals(list(page.sections.values_list("title", "visibility")), [("Changed studio FAQ Δ", "published")])
            equals(r.data["sections"][0]["title"], "Changed studio FAQ Δ")
        w.check = saved
    elif name == "admin-booking-website-release":
        BookingResourcePage.objects.filter(pk=page.pk).update(released=False)
        w.body = {"revision": 3, "released": True}
        w.check = lambda r: fields(page, released=True, revision=4)
    elif name == "admin-booking-website-assets":
        w.media = "multipart"
        w.body = lambda: {"file": image(), "alt_text": "New studio image Δ"}
        def uploaded(r):
            equals(page.assets.count(), 2)
            new = BookingResourcePageAsset.objects.get(pk=r.data["id"])
            fields(new, alt_text="New studio image Δ", page_id=page.pk, size_bytes=len(payload))
            equals(objects[new.object_key], payload)
            fields(page, revision=4)
        w.check = uploaded
    elif name == "admin-booking-website-asset":
        w.kwargs["asset_id"] = asset.pk
        if method == "GET":
            w.check = lambda r: equals((r["Content-Type"], r.content), ("image/webp", payload))
        else:
            def removed(r):
                equals(page.assets.count(), 0)
                equals(page.sections.get().asset_id, None)
                fields(page, revision=4)
            w.check = removed
    elif name.startswith("public-"):
        w.kwargs = {"makerspace_slug": w.tenant.slug, "public_token": w.room.public_token}
        w.foreign_pair = (200, None)
        w.off["bookings"] = (404, "not_found")
        if name == "public-booking-website-image":
            w.kwargs["asset_id"] = asset.pk
            w.check = lambda r: equals((r["Content-Type"], r.content), ("image/webp", payload))
        elif name == "public-booking-resource":
            def resource(r):
                equals(str(r.data["public_token"]), str(w.room.public_token))
                equals(r.data["name"], w.room.name)
                equals(r.data["website"]["sections"][0]["title"], "Retained studio FAQ")
            w.check = resource
            w.off["bookings.website"] = (200, None)
            w.policy_off = lambda key, r: equals((r.data["name"], r.data["website"]), (w.room.name, None))
        else:
            w.check = lambda r: equals((r.data["revision"], r.data["sections"][0]["title"]), (3, "Retained studio FAQ"))
        w.foreign_check = w.check
    else:
        w.check = lambda r: equals((r.data["revision"], r.data["sections"][0]["title"], r.data["assets"][0]["id"]),
            (3, "Retained studio FAQ", asset.pk))
