"""Wallet passes for guest passes (decision 223(k) P3, 223(l)).

A guest pass is a dated permit, not a card, so its wallet pass is STATIC: it carries the
makerspace name and logo, the holder's display name, the pass number, its validity and an
opaque QR token, and nothing else (no e-mail, phone or birth date). There is no update
web service: the pass expires on its own, and revocation lives on the server.

The QR token is stateless but REVOCABLE: `gp1.<pass id>.<hmac>`. Resolving it reads the live
`GuestPass` row, so a revoked, expired or converted pass answers "not valid" at once and
the copy in someone's wallet stops opening anything. Presence and desk check-in keep working
through the existing location check-in; the token only lets staff confirm a pass at the desk.
"""
import hashlib
import hmac

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit import services as audit
from apps.makerspaces.guest_pass_policy import guest_passes_on
from apps.makerspaces.guest_pass_queries import active_pass_for, payment_cleared, pass_entitlements
from apps.makerspaces.local_time import to_local
from apps.makerspaces.models import GuestPass
from apps.makerspaces.platform import feature_enabled

from .credentials import apple_for, configured_platforms, google_for

PREFIX = "gp1"
DOWNLOAD_SALT, DOWNLOAD_SECONDS = "guest-pass-wallet-pkpass", 60
KIND_LABELS = {"event": "Event guest", "sponsored": "Sponsored guest", "day": "Day pass"}


def _sig(guest_pass):
    key = hashlib.sha256(("guest-pass-wallet:" + settings.SECRET_KEY).encode()).digest()
    message = f"{guest_pass.pk}:{guest_pass.makerspace_id}:{guest_pass.holder_id}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:32]


def token_for(guest_pass):
    return f"{PREFIX}.{guest_pass.pk}.{_sig(guest_pass)}"


def resolve_token(token, makerspace=None):
    """The `GuestPass` a well-formed, authentic token names (any status), else None."""
    parts = (token or "").split(".")
    if len(parts) != 3 or parts[0] != PREFIX or not parts[1].isdigit():
        return None
    rows = GuestPass.objects.select_related("makerspace", "holder", "product").filter(pk=int(parts[1]))
    if makerspace is not None:
        rows = rows.filter(makerspace=makerspace)
    row = rows.first()
    return row if row is not None and hmac.compare_digest(parts[2], _sig(row)) else None


def scan(guest_pass, now=None):
    """What a desk scan reports: `{valid, reason, ...}`. Reads only; never changes the pass."""
    now = now or timezone.now()
    if guest_pass is None:
        return {"valid": False, "reason": "unknown", "pass_id": None, "holder_name": "", "kind": "",
                "valid_until": None, "entitlements": {}}
    reason = ""
    if not guest_passes_on(guest_pass.makerspace):
        reason = "off"
    elif guest_pass.status not in GuestPass.LIVE_STATUSES:
        reason = guest_pass.status
    elif now >= guest_pass.valid_until:
        reason = "expired"
    elif now < guest_pass.valid_from:
        reason = "not_yet_valid"
    elif active_pass_for(guest_pass.holder, guest_pass.makerspace, at=now) is None:
        reason = "unavailable"
    entitlements = pass_entitlements(guest_pass)
    return {"valid": not reason, "reason": reason, "pass_id": guest_pass.pk, "holder_name": _name(guest_pass),
            "kind": guest_pass.kind, "valid_until": guest_pass.valid_until,
            "entitlements": {"presence": entitlements.presence, "borrow": entitlements.borrow,
                             "machines": entitlements.machines}}


def _name(guest_pass):
    holder = guest_pass.holder
    name = (holder.display_name or holder.get_full_name() or "").strip()
    return name or gettext("Guest")


def content(guest_pass):
    """Everything the pass shows: the same shape `apple.pass_json` / `google.wallet_object` read."""
    space = guest_pass.makerspace
    local = to_local(space, guest_pass.valid_until)
    return {"issuer": (space.branding_config or {}).get("display_name") or space.name, "name": _name(guest_pass),
            "number": f"GP-{guest_pass.pk:06d}", "label": "Pass", "label_value": KIND_LABELS.get(guest_pass.kind, ""),
            "valid_until": local.strftime("%d %b %Y %H:%M"), "qr": token_for(guest_pass), "standing": "valid",
            "description": "guest pass", "expires_at": guest_pass.valid_until.isoformat()}


def platforms_for(guest_pass, now=None):
    """The wallet buttons to show: switch on, credentials resolved, and a pass that can still be used."""
    now = now or timezone.now()
    space = guest_pass.makerspace
    if not (guest_passes_on(space) and feature_enabled(space, "membership.wallet_passes")):
        return []
    if guest_pass.status not in GuestPass.LIVE_STATUSES or guest_pass.valid_until <= now:
        return []
    return list(configured_platforms(space)) if payment_cleared(guest_pass) else []


def _serial(guest_pass):
    return f"gp-{guest_pass.pk}-{_sig(guest_pass)[:12]}"


def download_token(guest_pass):
    return signing.dumps({"pass": guest_pass.pk}, salt=DOWNLOAD_SALT)


def pass_for_download(token):
    try:
        pass_id = signing.loads(token, salt=DOWNLOAD_SALT, max_age=DOWNLOAD_SECONDS)["pass"]
    except (signing.BadSignature, KeyError):
        raise NotFound() from None
    row = GuestPass.objects.select_related("makerspace", "holder", "product").filter(pk=pass_id).first()
    if row is None or "apple" not in platforms_for(row):
        raise NotFound()
    return row


def build_pkpass(guest_pass):
    from .apple import build_pkpass_bytes
    creds = apple_for(guest_pass.makerspace_id)
    if creds is None:
        raise NotFound()
    return build_pkpass_bytes(creds, _serial(guest_pass), content(guest_pass), makerspace=guest_pass.makerspace)


def issue_link(actor, guest_pass, platform, *, base_url=""):
    """`{platform, url, expires_in}` for the holder's own pass; audited, ids and platform only."""
    if platform not in platforms_for(guest_pass):
        raise ValidationError({"platform": gettext("Wallet passes are not available for this pass.")})
    if platform == "apple":
        url = f"{base_url}/api/v1/wallet/guest-pass/{download_token(guest_pass)}.pkpass"
        expires = DOWNLOAD_SECONDS
    else:
        from .google import link_for
        url, expires = link_for(google_for(guest_pass.makerspace_id), _serial(guest_pass).replace("-", "_"),
                                content(guest_pass)), None
    audit.record(actor, "wallet_pass.guest_issued", makerspace=guest_pass.makerspace, target=guest_pass,
                 meta={"pass_id": guest_pass.pk, "platform": platform})
    return {"platform": platform, "url": url, "expires_in": expires}
