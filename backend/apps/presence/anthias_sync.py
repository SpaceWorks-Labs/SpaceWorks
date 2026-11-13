"""Keep a space's Anthias players in step with its display screens (decision 325c).

For each player and each screen assigned to it this keeps ONE web asset: created on first sync, updated when
its name, duration or URL changes, deleted when the screen is unassigned or unpaired. `AnthiasAssetLink`
maps (player, screen) to the asset id, so a re-sync is idempotent and never duplicates. A failure marks the
player `error` with a short reason code and never raises into a request or loses other players' work.
"""
import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.secrets import decrypt_value
from apps.makerspaces.platform import feature_enabled
from apps.tenant_migration.gate_runtime import tenant_write
from .anthias_client import AnthiasClient, AnthiasError
from .models_anthias import AnthiasAssetLink, AnthiasPlayer

logger = logging.getLogger(__name__)
ASSET_YEARS = 10


def anthias_enabled(space):
    return feature_enabled(space, "display.anthias_push")


def display_origin(space):
    if space.frontend_domain and space.frontend_domain_status == "verified":
        return f"https://{space.frontend_domain}"
    return (getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").rstrip("/")


def display_url(row):
    """The screen's full URL, or `""` for a screen paired by code (it has no re-showable secret)."""
    secret = decrypt_value(row.link_secret_enc)
    origin = display_origin(row.makerspace)
    return f"{origin}/display#k={secret}" if secret and origin else ""


def cycle_seconds(row):
    """Anthias shows an asset for a fixed time, so it must cover one full rotation of the playlist."""
    if row.layout != "playlist":
        return 60
    slides = row.slide_seconds or {}
    return max(10, min(3600, sum(int(slides.get(p, row.rotation_seconds)) for p in row.panels)))


def asset_payload(row, order, now):
    # The name carries the screen id: Anthias v1.2 refuses a second asset with the same name.
    return {"name": f"SpaceWorks: {row.name or 'Display'} (#{row.pk})"[:256], "uri": display_url(row), "mimetype": "webpage",
            "duration": cycle_seconds(row), "is_enabled": True, "play_order": order, "skip_asset_check": 1,
            "start_date": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date": (now + timedelta(days=365 * ASSET_YEARS)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _hash(payload):
    stable = {k: v for k, v in payload.items() if k not in ("start_date", "end_date")}
    return hashlib.sha256(repr(sorted(stable.items())).encode()).hexdigest()


def _push_screen(client, player, row, order, now):
    payload = asset_payload(row, order, now)
    if not payload["uri"]:
        raise AnthiasError("no_link")
    digest = _hash(payload)
    link = AnthiasAssetLink.objects.filter(player=player, display=row).first()
    if link and link.synced_hash == digest:
        return
    uri_hash = hashlib.sha256(payload["uri"].encode()).hexdigest()
    if link and link.uri_hash != uri_hash:
        # Anthias's update serializer takes no `uri` (src/anthias_server/api/serializers/__init__.py), so a new
        # address means a new asset: remove the old one, then create.
        client.delete(link.asset_id)
        link.asset_id = client.create(payload)
    elif link:
        try:
            client.update(link.asset_id, payload)
        except AnthiasError as exc:
            if exc.reason != "not_found":
                raise
            link.asset_id = client.create(payload)  # someone deleted it on the player: recreate
    else:
        link = AnthiasAssetLink(player=player, display=row, asset_id=client.create(payload))
    link.synced_hash, link.uri_hash = digest, uri_hash
    link.save()


def _finish(player, actor, *, error=""):
    player.status = AnthiasPlayer.Status.ERROR if error else AnthiasPlayer.Status.OK
    player.last_error = error
    if not error:
        player.last_synced_at = timezone.now()
    player.save(update_fields=["status", "last_error", "last_synced_at", "api_version", "anthias_version"])
    audit.record(actor, "presence.anthias_synced", makerspace=player.makerspace, target=player,
                 meta={"ok": not error, "error": error})


def sync_player(player, actor=None):
    """Bring one player in step; returns the player (its `status`/`last_error` say how it went)."""
    space = player.makerspace
    with tenant_write(space.pk):
        if not anthias_enabled(space):
            return player
        try:
            client = AnthiasClient(player)
            player.api_version, player.anthias_version = client.detect()
            wanted = list(player.screens.select_related("makerspace").filter(revoked_at__isnull=True).order_by("pk"))
            now = timezone.now()
            for order, row in enumerate(wanted):
                _push_screen(client, player, row, order, now)
            keep = {row.pk for row in wanted}
            for link in list(player.links.exclude(display_id__in=keep)):
                client.delete(link.asset_id)
                link.delete()
        except AnthiasError as exc:
            _finish(player, actor, error=exc.reason)
        else:
            _finish(player, actor)
        return player


def test_player(player):
    """Health check for the form: `(ok, reason, api_version, anthias_version)`; saves what it learned."""
    try:
        api, version = AnthiasClient(player).detect()
    except AnthiasError as exc:
        return False, exc.reason, "", ""
    player.api_version, player.anthias_version = api, version
    player.save(update_fields=["api_version", "anthias_version"])
    return True, "", api, version


def remove_player_assets(player):
    """Delete the assets SpaceWorks made on a player before its row goes; best effort, never raises."""
    try:
        client = AnthiasClient(player)
        client.detect()
        for link in player.links.all():
            client.delete(link.asset_id)
    except AnthiasError:
        logger.warning("anthias_cleanup_failed")


def schedule_sync(row):
    """After a screen changes or is unpaired, queue a sync for every player showing it (post-commit)."""
    ids = list(row.players.values_list("pk", flat=True))
    if not ids:
        return
    from .tasks_anthias import sync_anthias_player_task
    for pk in ids:
        transaction.on_commit(lambda pk=pk: sync_anthias_player_task.delay(pk))
