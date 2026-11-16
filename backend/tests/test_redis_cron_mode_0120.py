"""Decision 339 / 337f B-5: Redis settings, key hygiene, and the "none (cron mode)" install at runtime.

The installer half of cron mode (questionnaire, overlay, selector) is pinned by
`tests/cloud/installer/test_redis_none_cron_mode.py`; this file pins what the running application does
with no Redis at all, plus the Celery transport and TTL rules from docs/architecture/redis.md.
"""

import json
import re
import ssl
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from django.test import RequestFactory

from config.settings_redis import VISIBILITY_TIMEOUT_SECONDS, celery_transport_settings
from tests.test_cloud_settings_conditions import import_settings

APPS = Path(__file__).resolve().parents[1] / "apps"
CRON_ENV = {"CLOUD_TASK_PROFILE": "brokerless", "CLOUD_SCHEDULER": "external", "CELERY_BROKER_URL": "",
            "CELERY_RESULT_BACKEND": "", "CELERY_TASK_ALWAYS_EAGER": "True", "CACHE_URL": "", "LIVE_REDIS_URL": ""}
PRINT = ("import json, config.settings as s; print(json.dumps({'cache': s.CACHES['default']['BACKEND'], "
         "'eager': s.CELERY_TASK_ALWAYS_EAGER, 'live': s.LIVE_REDIS_URL, "
         "'transport': hasattr(s, 'CELERY_BROKER_TRANSPORT_OPTIONS'), "
         "'ssl': str(getattr(s, 'CELERY_BROKER_USE_SSL', None))}))")


def _settings(**env):
    result = import_settings(PRINT, **env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_cron_mode_settings_need_no_redis_and_share_one_database_cache():
    values = _settings(**CRON_ENV)
    # Shared across gunicorn workers, so every rate limit holds; never per-process LocMem.
    assert values["cache"] == "django.core.cache.backends.db.DatabaseCache"
    assert values["eager"] is True and values["live"] == "" and values["transport"] is False


def test_a_rediss_broker_verifies_the_server_certificate_by_default():
    values = _settings(CELERY_BROKER_URL="rediss://:pw@redis.example:6380/0")
    assert values["transport"] is True
    assert "CERT_REQUIRED" in values["ssl"]


def test_celery_transport_settings_rules():
    assert celery_transport_settings("", None, eager=True) == {}
    plain = celery_transport_settings("redis://redis:6379/0", None, eager=False)
    assert plain["CELERY_BROKER_TRANSPORT_OPTIONS"]["visibility_timeout"] == VISIBILITY_TIMEOUT_SECONDS
    assert "CELERY_BROKER_USE_SSL" not in plain
    tls = celery_transport_settings("rediss://h:6380/0", "rediss://h:6380/1", eager=False)
    assert tls["CELERY_BROKER_USE_SSL"] == {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    assert tls["CELERY_REDIS_BACKEND_USE_SSL"] == {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    stated = celery_transport_settings("rediss://h:6380/0?ssl_cert_reqs=none", None, eager=False)
    assert "CELERY_BROKER_USE_SSL" not in stated  # the URL's own choice wins
    # Longer than the longest task, so acks_late never hands a running backup to a second worker.
    assert VISIBILITY_TIMEOUT_SECONDS >= 6 * 3600


def test_every_beat_task_also_runs_from_the_cron_scheduler():
    from apps.operations.cloud_jobs.catalog import legacy_schedule

    cron = {path for _name, path, _minutes in legacy_schedule()}
    beat = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}
    assert beat - cron == set(), "these beat tasks would never run in cron mode"


@pytest.mark.django_db
def test_api_client_last_seen_is_recorded_without_redis():
    from apps.apiclients import telemetry
    from apps.apiclients.models import ApiClient

    client, _secret = ApiClient.issue(label="cron client", allowed_origins=["https://c.example"],
                                      client_type="server", scopes=["public:read"])
    assert telemetry.get_redis_client() is None  # the test cache is not Redis, like cron mode
    request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.40")
    telemetry.record_signed_client_observation(request, client)
    assert telemetry.flush_usage_observations() == 1
    client.refresh_from_db()
    assert client.last_seen_at is not None
    assert telemetry.flush_usage_observations() == 0  # monotonic: re-reading the same value changes nothing


@pytest.mark.parametrize("profile,queued", [("brokerless", False), ("", True)])
def test_github_verification_never_runs_inline_without_a_worker(monkeypatch, settings, profile, queued):
    from django.core.cache import cache

    from apps.makerspaces import profile_github_queue, tasks

    settings.CLOUD_TASK_PROFILE = profile
    delay = MagicMock()
    monkeypatch.setattr(tasks.verify_github_ownership_task, "delay", delay)
    cache.delete("public-profile:github-verify-queued:42")
    profile_github_queue._dispatch(42)
    assert delay.called is queued


def test_cache_keys_without_expiry_are_only_the_bounded_last_known_good_ones():
    allowed = {"accounts/login_methods.py", "accounts/member_identity.py", "integrations/health_status.py",
               "managed_hosting/limit_defaults.py"}
    pattern = re.compile(r"cache\.set\([^\n]*(timeout=None|,\s*None\))")
    found = {path.relative_to(APPS).as_posix() for path in APPS.rglob("*.py")
             if "migrations" not in path.parts and pattern.search(path.read_text(encoding="utf-8"))}
    assert found <= allowed, f"cache keys with no expiry (one key each, or bound them): {sorted(found - allowed)}"


@pytest.mark.django_db
def test_public_profile_generations_expire_after_everything_they_version(monkeypatch, django_capture_on_commit_callbacks):
    from apps.makerspaces import profile_github, public_profile_cache

    writes = {}
    recorder = MagicMock()
    recorder.get.return_value = None
    recorder.set.side_effect = lambda key, value, timeout=None: writes.__setitem__(key, timeout)
    monkeypatch.setattr(public_profile_cache, "cache", recorder)
    with django_capture_on_commit_callbacks(execute=True):
        public_profile_cache.invalidate_profile("acct:7")
    assert writes["public-profile:generation:acct:7"] == public_profile_cache.GENERATION_TTL
    assert writes["public-profile:sitemap-generation"] == public_profile_cache.GENERATION_TTL
    assert public_profile_cache.GENERATION_TTL > profile_github.CALENDAR_TTL


def test_the_telegram_bot_name_cache_expires():
    from apps.integrations import notification_telegram

    assert 0 < notification_telegram.BOT_USERNAME_TTL <= 7 * 24 * 3600


def test_member_verification_throttle_never_puts_an_address_in_a_cache_key():
    from rest_framework.request import Request
    from rest_framework.parsers import JSONParser

    from apps.accounts.throttles import MemberVerificationEmailThrottle

    raw = RequestFactory().post("/", data=json.dumps({"email": "Person@Example.org"}), content_type="application/json")
    request = Request(raw, parsers=[JSONParser()])
    key = MemberVerificationEmailThrottle().get_cache_key(request, None)
    assert key and "person@example.org" not in key.lower()
    odd = Request(RequestFactory().post("/", data=json.dumps({"email": 12}), content_type="application/json"),
                  parsers=[JSONParser()])
    assert MemberVerificationEmailThrottle().get_cache_key(odd, None) is None  # anonymous, no address: no key
