"""Celery entry for Anthias sync: retried with backoff; an unreachable player never breaks anything else."""
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from .anthias_sync import sync_player
from .models_anthias import AnthiasPlayer

RETRYABLE = {"timeout", "unreachable", "dns_failed", "http_error"}
# Decision 332(a): one sync is a handful of calls of at most 4 s connect + 10 s read each (anthias_client), so two
# minutes covers a full player; past that the run stops, the player shows `timeout` and the retry backoff applies.
# The asset links already saved keep the next run idempotent.
SOFT_SECONDS, HARD_SECONDS = 120, 150


@shared_task(bind=True, max_retries=4, ignore_result=True, soft_time_limit=SOFT_SECONDS, time_limit=HARD_SECONDS)
def sync_anthias_player_task(self, player_id):
    player = AnthiasPlayer.objects.select_related("makerspace").filter(pk=player_id).first()
    if player is None:
        return
    try:
        sync_player(player)
    except SoftTimeLimitExceeded:
        _mark_timed_out(player)
    if player.status == AnthiasPlayer.Status.ERROR and player.last_error in RETRYABLE:
        raise self.retry(countdown=min(900, 30 * 2 ** self.request.retries))  # 30s, 1m, 2m, 4m


def _mark_timed_out(player):
    from apps.tenant_migration.gate_runtime import tenant_write
    with tenant_write(player.makerspace_id):
        AnthiasPlayer.objects.filter(pk=player.pk).update(status=AnthiasPlayer.Status.ERROR, last_error="timeout")
    player.status, player.last_error = AnthiasPlayer.Status.ERROR, "timeout"
