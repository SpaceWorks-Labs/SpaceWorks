"""The public "is this card valid?" check (SPEC §7, #71, #132).

Minimal by design: status, issuer, programme/plan/event, number and valid-until; the
holder's name and photo only with their opt-in (photo only while valid). Revoked
shows the issuer alone. Everything that should not be confirmed -- an unknown token,
a pending or rejected programme card, an erased holder, a switched-off feature, a
space that is unservable, archived or has the check turned off, or a request on
another tenant's host -- answers one uniform 404. No audit row per check: a daily
aggregate counter feeds the issuance report.
"""
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .holders import registered
from .models import CardVerifyCheckDay, CardVerifyToken
from .tokens import SHAPE

KIND_OF = {"member_card": "space", "programme_card": "organisation", "event_card": "event"}


def _count(makerspace_id):
    day = timezone.localdate()
    updated = CardVerifyCheckDay.objects.filter(makerspace_id=makerspace_id, day=day).update(count=F("count") + 1)
    if not updated:
        row, created = CardVerifyCheckDay.objects.get_or_create(makerspace_id=makerspace_id, day=day,
                                                                defaults={"count": 1})
        if not created:
            CardVerifyCheckDay.objects.filter(pk=row.pk).update(count=F("count") + 1)


def _host_ok(request, makerspace_id):
    if request is None:
        return True
    from apps.makerspaces.public_profile_access import _request_tenant_ids
    return all(pk == makerspace_id for pk in _request_tenant_ids(request))


def _photo_url(card):
    from .storage import signed_url
    key = getattr(card, "photo_object_key", "")
    if not key:
        return None
    try:
        return signed_url(key)
    except Exception:
        return None


def check(token, request=None):
    if not isinstance(token, str) or not SHAPE.match(token):
        raise NotFound()
    row = CardVerifyToken.objects.select_related("makerspace").filter(token=token).first()
    if row is None:
        raise NotFound()
    from apps.makerspaces.servability import is_servable
    kind = row.holder_kind
    spec = registered().get(kind)
    card = spec.model().objects.filter(pk=row.holder_id).first() if spec else None
    if (card is None or not is_servable(row.makerspace) or not spec.switched_on(card)
            or not spec.public_verify(card) or not _host_ok(request, row.makerspace_id)):
        raise NotFound()
    standing = spec.standing(card)
    if standing is None:
        raise NotFound()
    if row.retired_at is not None:
        standing = "revoked"
    _count(row.makerspace_id)
    issuer = spec.issuer(card)
    result = {"status": standing, "valid": standing == "valid", "issuer": issuer, "label": None, "number": None,
              "valid_until": None, "holder": None, "note": "", "checked_at": timezone.now()}
    if standing == "revoked":
        if row.retired_reason == CardVerifyToken.Retired.REISSUED:
            result["note"] = "A newer card was issued."
        return result
    values = spec.snapshot(card)
    result["label"] = _label(kind, card, values)
    result["number"] = values.get("number") or None
    result["valid_until"] = values.get("valid_until") or None
    name = values.get("name") if getattr(card, "verify_show_name", False) else None
    photo = _photo_url(card) if standing == "valid" and getattr(card, "verify_show_photo", False) else None
    if name or photo:
        result["holder"] = {"name": name, "photo_url": photo}
    return result


def _label(kind, card, values):
    if kind == "member_card":
        from apps.makerspaces.models import MemberCardSettings
        settings_row = MemberCardSettings.objects.filter(makerspace_id=card.makerspace_id).first()
        return values.get("plan") or None if settings_row is None or settings_row.verify_show_plan else None
    if kind == "programme_card":
        return values.get("programme") or None
    return values.get("event") or None
