"""Certificates on the shared Card Studio engine (decision 315): frozen snapshot -> document + RenderContext -> `draw_side`.

Dispatch (`uses_shared`): a v3 snapshot (a Studio certificate document) always renders here; a stored v2 snapshot renders
here only when issuance pinned `renderer: "shared"` into it (switch `CERTIFICATE_SHARED_RENDERER`, default OFF). The choice
is frozen per certificate, so a retried render of an already-issued certificate reproduces its original bytes.

Everything comes from the immutable snapshot: images through checksum-pinned `ImageResource`s, signatories from
`snapshot["signatures"]`, values from the frozen merge labels. Nothing is looked up by URL or id at render time.
"""
from django.conf import settings


def shared_switch_on():
    return bool(getattr(settings, "CERTIFICATE_SHARED_RENDERER", False))


def uses_shared(snapshot):
    version = snapshot.get("version")
    return version == 3 or (version == 2 and snapshot.get("renderer") == "shared" and not snapshot.get("legacy_background"))


def document_for(snapshot):
    if snapshot["version"] == 3:
        return snapshot
    from apps.card_designs.certificate_compile import compile_v2
    return compile_v2(snapshot)


def _hours(certificate):
    ends, starts = getattr(certificate, "event_ends_at", None), getattr(certificate, "event_starts_at", None)
    if not ends or not starts:
        return ""
    hours = round((ends - starts).total_seconds() / 3600 * 2) / 2
    return f"{hours:g}" if hours > 0 else ""


def values_for(certificate):
    """Merge values for the shared tag set: the v2 values plus recipient, serial, hours and achievement."""
    from .merge import frozen_merge, merge_values
    from .rendering import verification_url
    base = merge_values(certificate)
    serial = str(certificate.serial)
    return {**base, "recipient": base["name"], "event_date": base["eventDate"], "issue_date": base["issueDate"],
            "serial": serial, "serial_short": serial[:8].upper(), "hours": _hours(certificate),
            "achievement": frozen_merge(certificate).get("award", ""), "verify_url": verification_url(certificate)}


def _approved_slots(certificate, signatures):
    """Slots whose signatory approved this design revision. A preview (no stored revision) shows its samples as approved."""
    revision_id = getattr(certificate, "template_revision_id", None)
    event = getattr(certificate, "event", None) if revision_id else None
    slots = {int(slot) for slot in signatures}
    if event is None:
        return slots
    from .signatories import unapproved
    return slots - set(unapproved(event, revision_id, signatures))


def _resources(snapshot, document, *, preflight):
    from apps.events.certificate_artwork_storage import read_artwork
    from .layer_rendering import ImageResource
    assets, logos = {}, {}
    if preflight:
        return assets, logos
    for asset_id, item in (snapshot.get("artwork_resources") or {}).items():
        assets[asset_id] = ImageResource(read_artwork(item["key"], item["version"], item["sha256"]), item["sha256"]).content
    if snapshot.get("version") == 2 and snapshot.get("artwork_object_key"):  # a v2 `logo` layer prints the design artwork
        digest = snapshot["artwork_sha256"]
        logos["organisation"] = ImageResource(
            read_artwork(snapshot["artwork_object_key"], snapshot["artwork_version_id"], digest), digest).content
    return assets, logos


def _signatories(snapshot, document, certificate, *, preflight):
    from apps.events.certificate_artwork_storage import read_artwork
    from .layer_rendering import ImageResource
    signatures = snapshot.get("signatures") or {}
    approved = _approved_slots(certificate, signatures) if snapshot["version"] == 3 else {int(slot) for slot in signatures}
    result = {}
    for slot, item in signatures.items():
        art, image = item.get("artwork"), None
        if art and not preflight and int(slot) in approved:
            image = ImageResource(read_artwork(art["key"], art["version"], art["sha256"]), art["sha256"]).content
        result[int(slot)] = {"name": item["name"], "title": item["title"], "image": image, "approved": int(slot) in approved}
    return result


def _translation_keys(document):
    found = set()
    for side in ("front", "back"):
        for layer in (document.get(side) or {}).get("layers", ()):
            found.update(layer.get("translations") or {})
    return found


def locale_for(certificate, document):
    """The language a certificate prints in: the recipient's preferred language, else the event's space default.

    Only a language the design has translations for is chosen (full code, then its base language, e.g. ml-IN -> ml);
    otherwise "" and every layer prints its base text."""
    keys = _translation_keys(document)
    if not keys:
        return ""
    member = getattr(certificate, "recipient_member", None)
    event = getattr(certificate, "event", None)
    space = getattr(event, "makerspace", None)
    for code in (getattr(member, "preferred_locale", "") or "", getattr(space, "default_locale", "") or ""):
        for candidate in (code, code.split("-")[0]):
            if candidate and candidate in keys:
                return candidate
    return ""


def draw(canvas, certificate, *, preflight=False):
    from apps.card_designs.rendering import RenderContext, draw_side
    from .rendering import verification_url
    snapshot = certificate.layout_snapshot
    document = document_for(snapshot)
    assets, logos = _resources(snapshot, document, preflight=preflight)
    preview = str(certificate.serial) == "PREVIEW"
    context = RenderContext(values=values_for(certificate), verify_qr=verification_url(certificate), assets=assets,
                            logos=logos, signatories=_signatories(snapshot, document, certificate, preflight=preflight),
                            preview=preview, locale=locale_for(certificate, document))
    draw_side(canvas, document, "front", context)


def describe(canvas, certificate):
    """Document properties for a Studio certificate PDF (title is set by the caller)."""
    canvas.setCreator("Space Works")
    canvas.setAuthor(getattr(certificate, "issuer_name", "") or "Space Works")
    canvas.setSubject(getattr(certificate, "event_title", "") or "Certificate")
