from django.conf import settings
from zoneinfo import ZoneInfo
from .layer_rendering import ImageResource, QrResource, draw_document


def badge_image_resource(layer, *, event_id, document):
    """Resolve only promoted event artwork or a checksum-pinned packaged vector.

    The badge renderer must call this for image layers before the typed photo/QR
    handles. No profile selection, credential or arbitrary URL enters this path.
    """
    if layer["type"] != "image":
        return None
    from apps.events.models_certificate_templates import EventCertificateArtwork
    from apps.events.certificate_artwork_storage import read_artwork
    from .seed_artwork import render_packaged
    import hashlib
    row = EventCertificateArtwork.objects.filter(event_id=event_id,
        resource_id=layer["resource_id"], promoted_at__isnull=False).first()
    if row:
        return ImageResource(read_artwork(row.object_key, row.version_id, row.sha256), row.sha256)
    content = render_packaged(layer["resource_id"], width_mm=document["page_width_mm"],
                              height_mm=document["page_height_mm"])
    return ImageResource(content, hashlib.sha256(content).hexdigest())


def verification_url(certificate):
    # This canonical, public ID grants event/date/status only, never PDF access.
    return f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/certificates/verify/{certificate.serial}"


def merge_values(certificate):
    return {"name": certificate.recipient_name, "event": certificate.event_title,
            "eventDate": certificate.event_starts_at.astimezone(ZoneInfo(getattr(certificate, "event_timezone_name", "UTC"))).strftime("%d %B %Y"),
            "organisation": certificate.issuer_name,
            "issueDate": certificate.issued_at.strftime("%d %B %Y"),
            "certificate_id": str(certificate.serial), "crewRole": ""}


def render_layers(canvas, certificate, *, preflight=False):
    from apps.events.certificate_artwork_storage import read_artwork
    snapshot = certificate.layout_snapshot
    preview = str(certificate.serial) == "PREVIEW"
    if snapshot.get("legacy_background") and snapshot.get("artwork_object_key") and not preflight:
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from io import BytesIO
        content = read_artwork(snapshot["artwork_object_key"], snapshot["artwork_version_id"], snapshot["artwork_sha256"])
        canvas.drawImage(ImageReader(BytesIO(content)), 0, 0, width=snapshot["page_width_mm"]*mm,
                         height=snapshot["page_height_mm"]*mm, mask="auto")

    def resource(layer):
        if layer["type"] == "certificate_qr":
            return QrResource(verification_url(certificate), dummy=preview)
        if preflight:
            return None
        if layer["type"] == "image":
            item = snapshot["artwork_resources"][layer["resource_id"]]
            return ImageResource(read_artwork(item["key"], item["version"], item["sha256"]), item["sha256"])
        if layer["type"] == "logo" and snapshot.get("artwork_object_key"):
            digest = snapshot["artwork_sha256"]
            return ImageResource(read_artwork(snapshot["artwork_object_key"], snapshot["artwork_version_id"], digest), digest)
        return None

    draw_document(canvas, snapshot, merge_values(certificate), resource, preview=preview)
