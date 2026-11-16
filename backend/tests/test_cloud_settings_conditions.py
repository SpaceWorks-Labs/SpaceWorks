"""Import-time cloud settings, exercised in isolated interpreters without a database."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory

from config.client_ip import get_throttle_client_ip

BACKEND = Path(__file__).resolve().parents[1]


def import_settings(script, *, timeout=30, **overrides):
    environment = {
        **os.environ, "SECRET_KEY": "cloud-settings-test", "DEBUG": "True",
        "DATABASE_URL": "sqlite:///:memory:", "TRUSTED_PROXY_COUNT": "0",
        "SENTRY_DSN": "", "CACHE_URL": "", "CELERY_BROKER_URL": "",
        **overrides,
    }
    return subprocess.run(
        [sys.executable, "-c", "import environ; environ.Env.read_env = lambda *a, **k: None; " + script],
        cwd=BACKEND, env=environment, capture_output=True, text=True, timeout=timeout,
    )


def test_negative_proxy_count_refuses_startup():
    result = import_settings("import config.settings", TRUSTED_PROXY_COUNT="-1")
    assert result.returncode != 0
    assert "TRUSTED_PROXY_COUNT cannot be negative" in result.stderr


def test_axes_and_drf_must_agree_on_the_proxy_chain(settings):
    settings.AXES_IPWARE_PROXY_COUNT = 1
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    api_settings.reload()
    try:
        with pytest.raises(ImproperlyConfigured, match="must match"):
            get_throttle_client_ip(APIRequestFactory().get("/"))
    finally:
        api_settings.reload()


@pytest.mark.parametrize("url,backend", [
    ("", "django.core.cache.backends.db.DatabaseCache"),
    # Decision 339: Redis is wrapped so an outage degrades throttles instead of failing every request.
    ("redis://cache:6379/1", "config.redis_cache.ResilientRedisCache"),
])
def test_redis_and_database_cache_selection(url, backend):
    result = import_settings(
        "import config.settings as s; print(s.CACHES['default']['BACKEND'])", CACHE_URL=url,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == backend


def test_forwarded_proto_setting_changes_djangos_secure_request_detection():
    result = import_settings(
        "import config.settings as s; print(s.SECURE_PROXY_SSL_HEADER)",
        TRUST_X_FORWARDED_PROTO="true",
    )
    assert result.returncode == 0, result.stderr
    assert "('HTTP_X_FORWARDED_PROTO', 'https')" in result.stdout


def test_sentry_unset_never_imports_the_sdk():
    result = import_settings(
        "import sys; import config.settings; print('sentry_sdk' in sys.modules)"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "False"


@pytest.mark.parametrize("provider", ["smtp", "resend", "brevo", "mailgun", "postmark", "sendgrid", "ses"])
@pytest.mark.parametrize("mode,profile", [("host", "full"), ("managed", "full"), ("managed", "free")])
def test_explicit_email_provider_boots_without_replacing_legacy_backend(provider, mode, profile):
    script = """
import django, json
django.setup()
from django.conf import settings as s
print(json.dumps([s.EMAIL_BACKEND, s.EMAIL_PROVIDER, s.EMAIL_PROVIDER_CONFIG_FILE,
                  s.EMAIL_PROVIDER_WEBHOOKS_ENABLED, 'anymail' in s.INSTALLED_APPS]))
"""
    # The fresh Django app registry can take over 30 seconds on an isolated bind mount.
    result = import_settings(script, timeout=120, EMAIL_PROVIDER=provider,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_PROVIDER_CONFIG_FILE="/private/mail.json", EMAIL_PROVIDER_WEBHOOKS_ENABLED="True",
        SPACEWORKS_DEPLOYMENT_MODE=mode, SPACEWORKS_DEPLOYMENT_PROFILE=profile,
        SPACEWORKS_SECRET_FILE_MODE="native", DATABASE_CONNECTION_MODE="direct",
        DATABASE_URL="postgres://runtime:password@db.example.test:5432/spaceworks?sslmode=require",
        CLOUD_TASK_PROFILE="brokerless", CLOUD_SCHEDULER="tick" if profile == "free" else "loop",
        CELERY_RESULT_BACKEND="", LIVE_REDIS_URL="", CELERY_TASK_ALWAYS_EAGER="True",
        ALLOWED_HOSTS="api.example.test", FREE_TICK_INTERVAL_SECONDS="600", FREE_TICK_BUDGET_SECONDS="20",
        TRUST_FORWARDED_HOST="False", STORAGE_CAPABILITIES_FILE="", SENTRY_DSN="")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == [
        "django.core.mail.backends.locmem.EmailBackend", provider, "/private/mail.json", True, False,
    ]


def test_sentry_configured_has_both_integrations_and_no_default_pii():
    script = """
import json, sys, types
sdk = types.ModuleType('sentry_sdk')
sdk.init = lambda **values: print(json.dumps({**values, 'integrations': [type(v).__name__ for v in values['integrations']]}, default=lambda hook: hook.__name__))
sys.modules['sentry_sdk'] = sdk
for name in ('Celery', 'Django'):
    module = types.ModuleType('sentry_sdk.integrations.' + name.lower())
    setattr(module, name + 'Integration', type(name + 'Integration', (), {}))
    sys.modules[module.__name__] = module
import config.settings
"""
    result = import_settings(script, SENTRY_DSN="https://key@sentry.example/1", SENTRY_TRACES_SAMPLE_RATE="0.0")
    assert result.returncode == 0, result.stderr
    values = json.loads(result.stdout.strip().splitlines()[-1])
    assert values["integrations"] == ["DjangoIntegration", "CeleryIntegration"]
    assert values["send_default_pii"] is False
    # The privacy scrubbers (config.sentry_privacy) are wired for events and for transactions.
    assert values["before_send"] == "before_send" and values["before_send_transaction"] == "before_send_transaction"
    assert values["traces_sample_rate"] == 0.0
