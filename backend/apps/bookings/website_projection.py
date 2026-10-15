"""Public data never contains storage keys, reservations, answers or internal buffers."""

from django.http import Http404
from .website_visibility import page_for, visible_page

SECTION_FIELDS = ("kind", "slug", "title", "body", "url", "visibility", "position")


def project(space, *, public=False):
    from apps.makerspaces.website_directory import public_url
    page = visible_page(space) if public else page_for(space)
    result = {"revision": 0, "released": False, "sections": [],
              "public_url": public_url(space.makerspace, "bookings", space.public_token),
              "embed_path": f"/embed/{space.makerspace.slug}/bookings/{space.public_token}/"}
    if not public:
        result["assets"] = []
    if page is None:
        return result
    prefix = (f"/api/v1/public/{space.makerspace.slug}/spaces/{space.public_token}/website/assets/"
              if public else f"/api/v1/admin/spaces/{space.pk}/website/assets/")
    rows = page.sections.select_related("asset")
    if public:
        rows = rows.filter(visibility="published")
    result.update(revision=page.revision, released=page.released, sections=[{
        **{field: getattr(row, field) for field in SECTION_FIELDS},
        "asset_id": row.asset_id, "image_url": f"{prefix}{row.asset_id}/" if row.asset_id else None,
        "image_alt_text": row.asset.alt_text if row.asset_id else "",
    } for row in rows])
    if not public:
        result["assets"] = list(page.assets.values("id", "size_bytes", "alt_text"))
    return result


def detail(space):
    from .serializers_public import PublicBookableSpaceSerializer
    from apps.payments.models import MakerspacePaymentSettings
    settings = MakerspacePaymentSettings.objects.filter(makerspace=space.makerspace).first()
    try:
        website = project(space, public=True)
    except Http404:
        website = None
    return {**PublicBookableSpaceSerializer(space).data,
            "payment_amount": space.payment_amount,
            "currency": settings.default_currency if settings else MakerspacePaymentSettings._meta.get_field("default_currency").default,
            "rules": {key: getattr(space, field) for key, field in (
                ("minimum_minutes", "min_booking_duration_minutes"),
                ("maximum_minutes", "max_booking_duration_minutes"),
                ("lead_minutes", "booking_lead_time_minutes"),
                ("advance_days", "max_booking_advance_days"),
                ("cancellation_cutoff_hours", "cancellation_cutoff_hours"),
            )}, "website": website}
