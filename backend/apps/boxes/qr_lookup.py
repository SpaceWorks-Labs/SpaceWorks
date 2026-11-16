"""What a scanned QR string resolves to: a SpaceWorks payload OR an external label value.

Every scan surface (scanner, scan, stocktake, self-checkout, direct handout and return,
reviewed-request unit issue, kiosk, kit preview) filters through `scanned_q`, so a label
printed outside SpaceWorks works everywhere a SpaceWorks label does. External values are
unique only per makerspace, so a lookup that is not already pinned to one makerspace
must go through `pick_scanned`, which refuses an ambiguous match instead of guessing.
"""
from django.db.models import Q
from django.http import Http404

from apps.boxes.models import QrCode

EXTERNAL_VALUE_MAX_LENGTH = 64


def normalize_scanned(value):
    """Trim surrounding whitespace only; case is preserved (labels are opaque)."""
    return str(value or "").strip()


def scanned_q(value):
    value = normalize_scanned(value)
    return Q(payload=value) | Q(source=QrCode.Source.EXTERNAL, external_value=value)


def scanned_in_q(values):
    values = {normalize_scanned(value) for value in values}
    return Q(payload__in=values) | Q(source=QrCode.Source.EXTERNAL, external_value__in=values)


def label_value(qr):
    """The string the physical label encodes -- what printing must render."""
    return qr.external_value if qr.source == QrCode.Source.EXTERNAL else qr.payload


def scanned_keys(qr):
    """Every client string that may name this QR (payload always; the label when external)."""
    keys = {qr.payload}
    if qr.source == QrCode.Source.EXTERNAL:
        keys.add(qr.external_value)
    return keys


def by_scanned_key(qrs):
    return {key: qr for qr in qrs for key in scanned_keys(qr)}


def pick_scanned(queryset, value):
    """One QR for a scanned string, or None when unknown or ambiguous across makerspaces.

    A payload match wins (payloads are deployment-unique). External matches count only
    when exactly one makerspace in scope has the value.
    """
    value = normalize_scanned(value)
    if not value:
        return None
    payload_match = queryset.filter(payload=value).first()
    if payload_match is not None:
        return payload_match
    matches = list(queryset.filter(source=QrCode.Source.EXTERNAL, external_value=value)[:2])
    return matches[0] if len(matches) == 1 else None


def scanned_or_404(queryset, value):
    qr = pick_scanned(queryset, value)
    if qr is None:
        raise Http404
    return qr
