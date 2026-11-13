"""Who is at the adapter: NFC tag, member number + PIN, or member-card QR + PIN (lead 1, M6, decision 336j).

* **Identification is not authentication.** A member card's desk QR says WHO; at an adapter it opens nothing on its
  own and must come with that member's PIN (``pin``). A public card check link (``/verify/c/<token>``) or a bare
  43-character check token is never an adapter credential: it is printed for strangers to verify a card.
* **One denial for every member-level failure.** Unknown member number or card, no PIN set, wrong PIN, locked or
  disabled credential all answer ``unknown_credential``, so a keypad cannot learn who has a PIN. The precise cause
  goes to the server log only (no secret in it). ``pin_required`` asks the adapter to prompt for a PIN after a card
  QR; it is returned before any lookup, so it reveals nothing about the card.
* **Attempt budgets.** Besides the per-member lock (5 wrong PINs in a row lock that credential for 15 minutes), every
  binding and every space has a failure budget per 15-minute window in the shared cache. An exhausted budget makes
  that binding (or the whole space) refuse PIN and card-QR attempts with ``too_many_attempts`` for a cooldown that
  doubles each time it trips again within a day (5 minutes up to 24 hours). The budget is checked BEFORE the PIN,
  so a right guess during a cooldown still opens nothing. A cache failure raises, and every caller fails closed.
"""
import hmac
import logging
import re
from datetime import timedelta

from django.core.cache import cache

from apps.devices.models import AdapterCredential
from apps.devices.services_adapter_core import credential_digest

logger = logging.getLogger(__name__)
DENIED = "unknown_credential"
BUSY = "too_many_attempts"
PIN_REQUIRED = "pin_required"
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15
WINDOW_SECONDS = 900
BUDGETS = {"binding": 10, "space": 30}
BASE_COOLDOWN = 300
MAX_COOLDOWN = 86400
DESK = re.compile(r"^[0-9a-f]{32}$")
GUESSABLE = ("pin", "card_qr")


def _user(user_id):
    from apps.accounts.models import User
    return User.objects.filter(pk=user_id, is_active=True).first() if user_id else None


def _scopes(makerspace, binding):
    scopes = [("space", makerspace.pk, BUDGETS["space"])]
    if binding is not None:
        scopes.insert(0, ("binding", binding.pk, BUDGETS["binding"]))
    return scopes


def cooling_down(makerspace, binding):
    return any(cache.get(f"adapter-pin-block:{kind}:{key}") for kind, key, _ in _scopes(makerspace, binding))


def _count(key, ttl):
    cache.add(key, 0, ttl)
    return cache.incr(key)


def cooldown_for(level):
    """5 minutes the first time a budget trips, doubling each time it trips again within a day, at most a day."""
    return min(BASE_COOLDOWN * 2 ** min(level - 1, 16), MAX_COOLDOWN)


def record_failure(makerspace, binding):
    """Charge one failed guess to the binding and the space; trip a doubling cooldown when a budget runs out."""
    for kind, key, budget in _scopes(makerspace, binding):
        if _count(f"adapter-pin-fail:{kind}:{key}", WINDOW_SECONDS) < budget:
            continue
        level = _count(f"adapter-pin-level:{kind}:{key}", MAX_COOLDOWN)
        cooldown = cooldown_for(level)
        cache.set(f"adapter-pin-block:{kind}:{key}", 1, cooldown)
        cache.delete(f"adapter-pin-fail:{kind}:{key}")
        logger.warning("adapter credential budget exhausted", extra={"scope": kind, "scope_id": str(key),
                                                                     "cooldown_seconds": cooldown})


def _by_card_number(makerspace, number):
    from apps.makerspaces.models import MemberCard
    try:
        value = int(str(number).strip())
    except (TypeError, ValueError):
        return None
    card = MemberCard.objects.select_related("membership").filter(
        makerspace=makerspace, card_number=value, revoked_at__isnull=True).first()
    return card.membership.user_id if card is not None and card.is_active and card.membership else None


def _by_desk_qr(makerspace, payload):
    """The holder of an ACTIVE member-card desk QR in this space; public check links and tokens find nobody."""
    from apps.boxes.models import QrCode
    from apps.makerspaces.models import MemberCard
    payload = (payload or "").strip()
    if not DESK.match(payload):
        return None
    qr = QrCode.objects.filter(payload=payload, makerspace=makerspace, target_type=QrCode.TargetType.MEMBER_CARD,
                               status=QrCode.Status.ACTIVE).first()
    if qr is None:
        return None
    card = MemberCard.objects.select_related("membership").filter(pk=qr.target_id, makerspace=makerspace).first()
    return card.membership.user_id if card is not None and card.is_active and card.membership else None


def _check_pin(makerspace, user_id, pin, now):
    """'ok' or the precise cause of a refusal (for the server log only)."""
    if user_id is None:
        return "unknown_member"
    row = AdapterCredential.objects.select_for_update().filter(
        makerspace=makerspace, user_id=user_id, kind="pin", disabled_at__isnull=True).first()
    if row is None:
        return "no_pin"
    if row.locked_until and row.locked_until > now:
        return "locked"
    digest = credential_digest(makerspace.pk, "pin", pin, user_id=user_id)
    if not hmac.compare_digest(row.digest.encode("ascii"), digest.encode("ascii")):
        row.failed_attempts += 1
        row.locked_until = now + timedelta(minutes=LOCK_MINUTES) if row.failed_attempts >= MAX_FAILED_ATTEMPTS else None
        if row.locked_until:
            row.failed_attempts = 0
        row.save(update_fields=["failed_attempts", "locked_until"])
        return "wrong_pin"
    row.failed_attempts, row.locked_until, row.last_used_at = 0, None, now
    row.save(update_fields=["failed_attempts", "locked_until", "last_used_at"])
    return "ok"


def _nfc(makerspace, value, now):
    digest = credential_digest(makerspace.pk, "nfc", value)
    row = AdapterCredential.objects.select_for_update().filter(makerspace=makerspace, kind="nfc", digest=digest).first()
    if row is None or row.disabled_at is not None:
        return None
    row.failed_attempts, row.locked_until, row.last_used_at = 0, None, now
    row.save(update_fields=["failed_attempts", "locked_until", "last_used_at"])
    return _user(row.user_id)


def resolve(makerspace, credential, now, *, binding=None):
    """(member, reason): reason is 'ok', ``unknown_credential``, ``pin_required`` or ``too_many_attempts``."""
    kind = credential["type"]
    if kind not in GUESSABLE:
        member = _nfc(makerspace, credential["value"], now)
        return (member, "ok") if member is not None else (None, DENIED)
    if kind == "card_qr" and not credential.get("pin"):
        return None, PIN_REQUIRED
    if cooling_down(makerspace, binding):
        return None, BUSY
    if kind == "card_qr":
        user_id, pin = _by_desk_qr(makerspace, credential["value"]), credential["pin"]
    else:
        user_id, pin = _by_card_number(makerspace, credential.get("member_number")), credential["value"]
    cause = _check_pin(makerspace, user_id, pin, now)
    member = _user(user_id) if cause == "ok" else None
    if member is None:
        record_failure(makerspace, binding)
        logger.info("adapter credential refused", extra={"credential_type": kind, "cause": cause,
                                                         "binding_id": str(getattr(binding, "pk", ""))})
        return None, DENIED
    return member, "ok"
