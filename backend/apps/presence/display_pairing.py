"""Pairing, configuring and unpairing space display screens (decision 307c).

Flow: the screen calls `register()` (anonymous) and keeps the returned secret; staff call `claim()` with
the code the screen shows; the screen then polls with its secret and receives its panels. Every staff
write audits (claim, config change, unpair). Unpairing sets `revoked_at`, so the very next poll fails and
the secret is dead for good; a screen needs a fresh registration to come back.
"""
import hashlib
import ipaddress
import secrets
from datetime import timedelta

from django.core.cache import cache

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.secrets import encrypt_value
from apps.tenant_migration.gate_runtime import tenant_write
from .display_config import clean_display_settings, clean_panels
from .models_display import DEFAULT_ROTATION, MAX_ROTATION, MIN_ROTATION, DisplayScreen
from .policy import PresenceError, require_enabled, require_staff

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L: read aloud across a room
CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=30)
MAX_UNCLAIMED = 2000
# L-D2: one network (an IPv4 address, or an IPv6 /64, which one household or attacker owns whole) may hold
# only this many screens waiting to be paired, so a few hosts cannot fill the platform-wide registry.
MAX_UNCLAIMED_PER_NETWORK = 20
NETWORK_KEY = "presence:display-register:{}"
# L-D2: wrong pairing codes a space may try per hour, on top of the per-user DRF throttle on the route.
CLAIM_FAILURES_PER_SPACE = 30
CLAIM_FAILURE_KEY = "presence:display-claim-failures:{}"
LIMIT_KEY = "paired_displays"
SETTING_FIELDS = ("layout", "theme", "privacy", "refresh_seconds", "slide_seconds")


def digest(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def display_enabled(space):
    return feature_enabled(space, "presence.public_display")


def require_display(space):
    require_enabled(space)
    if not display_enabled(space):
        raise NotFound()


def network_of(ip):
    """The registry budget key for a client address: the address for IPv4, its /64 for IPv6."""
    try:
        address = ipaddress.ip_address(str(ip or "").split("%", 1)[0])
    except ValueError:
        return "unknown"
    mapped = getattr(address, "ipv4_mapped", None)  # IPv4Address has no such attribute
    if address.version == 6 and mapped is None:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(mapped or address)


def _bump(key, seconds):
    cache.add(key, 0, timeout=seconds)
    try:
        return cache.incr(key)
    except ValueError:  # evicted between add and incr: start again
        cache.set(key, 1, timeout=seconds)
        return 1


def _charge_network(network):
    """Count one registration against the network's live budget (a window as long as a code lives)."""
    key = NETWORK_KEY.format(hashlib.sha256(network.encode()).hexdigest()[:32])
    return _bump(key, int(CODE_TTL.total_seconds())) <= MAX_UNCLAIMED_PER_NETWORK


def register(now=None, *, client_ip=None):
    """A new unclaimed screen: `(row, secret)`. Expired unclaimed rows are swept here."""
    now = now or timezone.now()
    DisplayScreen.objects.filter(makerspace__isnull=True, code_expires_at__lt=now).delete()
    if DisplayScreen.objects.filter(makerspace__isnull=True).count() >= MAX_UNCLAIMED or not _charge_network(
            network_of(client_ip)):
        raise PresenceError("display_registry_full", gettext("Too many screens are waiting to be paired."),
                            status_code=429)
    secret = secrets.token_urlsafe(32)
    for _ in range(8):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        try:
            with transaction.atomic():
                row = DisplayScreen.objects.create(token_digest=digest(secret), pairing_code=code,
                                                   code_expires_at=now + CODE_TTL)
            return row, secret
        except IntegrityError:
            continue
    raise PresenceError("display_code_unavailable", gettext("Try again."), status_code=503)


def resolve(token):
    """The live, claimed-or-waiting screen for a secret, else the one 404 (unknown and revoked look alike)."""
    row = DisplayScreen.objects.select_related("makerspace").filter(token_digest=digest(token)).first()
    if row is None or row.revoked_at is not None:
        raise NotFound()
    return row


def touch(row, now=None):
    now = now or timezone.now()
    if row.last_seen_at is None or now - row.last_seen_at > timedelta(seconds=30):
        DisplayScreen.objects.filter(pk=row.pk).update(last_seen_at=now)


def clean_config(values, *, current=None):
    """Validated config fields from request data; unknown panels and out-of-range seconds are 400s."""
    result = {}
    if "panels" in values:
        result["panels"] = clean_panels(values["panels"])
    if "rotation_seconds" in values:
        seconds = values["rotation_seconds"]
        if type(seconds) is not int or not MIN_ROTATION <= seconds <= MAX_ROTATION:
            raise PresenceError("invalid_rotation", gettext("Rotation must be between %(lo)s and %(hi)s seconds.")
                                % {"lo": MIN_ROTATION, "hi": MAX_ROTATION})
        result["rotation_seconds"] = seconds
    for field, limit in (("name", 80), ("announcement", 280)):
        if field in values:
            text = values[field]
            if not isinstance(text, str) or len(text.strip()) > limit:
                raise PresenceError(f"invalid_{field}", gettext("That text is too long."))
            result[field] = text.strip()
    result.update(clean_display_settings(values))
    return result


def claim(actor, space, code, values):
    """Pair the waiting screen showing `code`. Wrong codes are audited and spend the space's hourly budget."""
    from apps.managed_hosting.extra_quotas import check_extra_quota
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        require_display(space)
        config = clean_config(values)
        code = str(code or "").strip().upper()
        if (cache.get(CLAIM_FAILURE_KEY.format(space.pk)) or 0) >= CLAIM_FAILURES_PER_SPACE:
            raise PresenceError("display_claim_throttled",
                                gettext("Too many wrong codes. Wait an hour, then try again."), status_code=429)
        with transaction.atomic():
            row = (DisplayScreen.objects.select_for_update().filter(
                makerspace__isnull=True, pairing_code=code, revoked_at__isnull=True,
                code_expires_at__gt=timezone.now()).first() if code else None)
            if row is not None:
                check_extra_quota(space, LIMIT_KEY)  # decision 284: typed 409 paired_displays_quota_reached
                row.makerspace, row.pairing_code, row.claimed_at = space, "", timezone.now()
                row.panels = config.get("panels") or ["here_now", "calendar", "machines"]
                row.rotation_seconds = config.get("rotation_seconds", DEFAULT_ROTATION)
                row.name = config.get("name", "")
                row.announcement = config.get("announcement", "")
                for key in SETTING_FIELDS:
                    if key in config:
                        setattr(row, key, config[key])
                row.save()
                audit.record(actor, "presence.display_claimed", makerspace=space, target=row,
                             meta={"panels": row.panels, "rotation_seconds": row.rotation_seconds})
                return row
        failures = _bump(CLAIM_FAILURE_KEY.format(space.pk), 3600)
        audit.record(actor, "presence.display_claim_failed", makerspace=space, meta={"failures": failures})
        raise PresenceError("invalid_pairing_code",
                            gettext("That code is not recognised or has expired. Check the screen."),
                            status_code=404)


def _owned(space, pk):
    row = DisplayScreen.objects.select_for_update().filter(pk=pk, makerspace=space, revoked_at__isnull=True).first()
    if row is None:
        raise NotFound()
    return row


def update(actor, space, pk, values):
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        require_display(space)
        config = clean_config(values)
        with transaction.atomic():
            row = _owned(space, pk)
            changed = sorted(k for k, v in config.items() if getattr(row, k) != v)
            for key, value in config.items():
                setattr(row, key, value)
            if changed:
                row.config_version += 1
                row.save()
                audit.record(actor, "presence.display_updated", makerspace=space, target=row,
                             meta={"fields": changed})
                from .anthias_sync import schedule_sync
                schedule_sync(row)  # a changed screen changes its Anthias asset (name, duration)
        return row


def provision(actor, space, values):
    """A screen created by staff with its link already issued (no code): `(row, secret)`.

    This is the Anthias path: the player's browser cannot type a pairing code, so the URL itself carries
    the screen's secret. Its digest authenticates polls; an encrypted copy is kept only so the Anthias sync
    can push the address to players. The staff API returns the address on provision and rotate only
    (L-D3); a lost address is replaced with "New address", never read back.
    """
    from apps.managed_hosting.extra_quotas import check_extra_quota
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        require_display(space)
        config = clean_config(values)
        secret = secrets.token_urlsafe(32)
        with transaction.atomic():
            check_extra_quota(space, LIMIT_KEY)
            row = DisplayScreen(makerspace=space, token_digest=digest(secret), code_expires_at=timezone.now(),
                                claimed_at=timezone.now(), link_secret_enc=encrypt_value(secret), panels=config.pop("panels", None) or ["here_now", "calendar", "machines"])
            for key, value in config.items():
                setattr(row, key, value)
            row.save()
            audit.record(actor, "presence.display_provisioned", makerspace=space, target=row,
                         meta={"panels": row.panels})
        return row, secret


def rotate_link(actor, space, pk):
    """Issue a new secret for a screen: the old URL stops working at once. Returns `(row, secret)`."""
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        require_display(space)
        secret = secrets.token_urlsafe(32)
        with transaction.atomic():
            row = _owned(space, pk)
            row.token_digest, row.link_secret_enc = digest(secret), encrypt_value(secret)
            row.save(update_fields=["token_digest", "link_secret_enc"])
            audit.record(actor, "presence.display_link_rotated", makerspace=space, target=row)
        return row, secret


def unpair(actor, space, pk):
    # Needs only the presence module: while the switch is off the feed is already a 404, so a token is inert.
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        with transaction.atomic():
            row = _owned(space, pk)
            row.revoked_at = timezone.now()
            row.save(update_fields=["revoked_at"])
            audit.record(actor, "presence.display_unpaired", makerspace=space, target=row)
            from .anthias_sync import schedule_sync
            schedule_sync(row)  # the screen's assets are removed from every player showing it
        return row


def set_players(actor, space, pk, player_ids):
    """Choose which Anthias players show this screen; the sync queued after commit makes the assets match."""
    from .models_anthias import AnthiasPlayer
    with tenant_write(space.pk):
        require_staff(actor, space, settings=True)
        with transaction.atomic():
            row = _owned(space, pk)
            players = list(AnthiasPlayer.objects.filter(makerspace=space, pk__in=player_ids))
            if len(players) != len(set(player_ids)):
                raise NotFound()
            before = set(row.players.values_list("pk", flat=True))
            row.players.set(players)
            affected = before | {p.pk for p in players}
            if affected != (before & {p.pk for p in players}):
                audit.record(actor, "presence.display_players_changed", makerspace=space, target=row,
                             meta={"players": sorted(p.pk for p in players)})
                from .tasks_anthias import sync_anthias_player_task
                for player_pk in affected:
                    transaction.on_commit(lambda pk=player_pk: sync_anthias_player_task.delay(pk))
        return row
