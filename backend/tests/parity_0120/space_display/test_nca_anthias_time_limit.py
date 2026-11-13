"""NCA audit 0.12.0 (decision 332a): an Anthias sync that hits its soft time limit marks the player `timeout`
(a retryable reason) instead of leaving a stale status behind."""
import pytest
from celery.exceptions import SoftTimeLimitExceeded

from apps.presence import tasks_anthias
from apps.presence.models_anthias import AnthiasPlayer

from .test_anthias import FakeAnthias, _player, _screen, anthias  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def test_a_sync_cut_by_the_soft_time_limit_records_a_retryable_timeout(anthias):  # noqa: F811
    admin, _screen_row = _screen(anthias)
    anthias.install(FakeAnthias("v2"))
    pid = _player(anthias, admin).json()["id"]
    player = AnthiasPlayer.objects.get(pk=pid)
    try:
        raise SoftTimeLimitExceeded()  # what Celery raises inside sync_player when the soft limit is reached
    except SoftTimeLimitExceeded:
        tasks_anthias._mark_timed_out(player)
    player.refresh_from_db()
    assert player.status == AnthiasPlayer.Status.ERROR and player.last_error == "timeout"
    assert "timeout" in tasks_anthias.RETRYABLE
    assert tasks_anthias.sync_anthias_player_task.soft_time_limit < tasks_anthias.sync_anthias_player_task.time_limit
