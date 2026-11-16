"""Fresh interpreters prove URL/schema isolation with all free settings present."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from django.urls import Resolver404, resolve

TICK = "/api/v1/internal/free/tick"


def test_full_profile_does_not_resolve_tick_even_when_secret_is_set(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.FREE_TICK_SECRET = "verification-secret"
    with pytest.raises(Resolver404):
        resolve(TICK)


@pytest.mark.parametrize("mode", ["host", "managed"])
@pytest.mark.parametrize("profile", [None, "full"])
@pytest.mark.parametrize("tasks", ["redis", "brokerless"])
def test_full_boot_schema_imports_are_isolated_from_every_free_setting(mode, profile, tasks):
    backend = Path(__file__).resolve().parents[3]
    script = """
import sys, django
django.setup()
from django.urls import Resolver404, resolve
from drf_spectacular.generators import SchemaGenerator
try:
    resolve('/api/v1/internal/free/tick')
except Resolver404:
    pass
else:
    raise AssertionError('full_tick_resolves')
schema = SchemaGenerator().get_schema(request=None, public=True)
assert '/api/v1/internal/free/tick' not in schema['paths']
assert not any(name.startswith(('apps.operations.cloud_jobs.tick_',
                               'apps.operations.cloud_quotas')) for name in sys.modules)
"""
    # Managed mode refuses an undeclared transport, so declare the direct one explicitly.
    environment = {**os.environ, "SPACEWORKS_DEPLOYMENT_MODE": mode, "DATABASE_CONNECTION_MODE": "direct",
                   "DJANGO_SETTINGS_MODULE": "config.settings", "CLOUD_TASK_PROFILE": tasks,
                   "CLOUD_SCHEDULER": "beat" if tasks == "redis" else "loop",
                   "CELERY_BROKER_URL": "redis://unreachable.invalid:6379/0" if tasks == "redis" else "",
                   "FREE_TICK_SECRET": "verification-secret", "FREE_TICK_BUDGET_SECONDS": "20",
                   "FREE_TICK_INTERVAL_SECONDS": "600", "FREE_TICK_RATE_LIMIT_PER_MINUTE": "6",
                   "FREE_EMAIL_DAILY_CAP": "1", "FREE_EMAIL_MONTHLY_CAP": "1",
                   "FREE_DB_CAP_BYTES": "1", "FREE_OBJECT_CAP_BYTES": "1"}
    if profile is None:
        environment.pop("SPACEWORKS_DEPLOYMENT_PROFILE", None)
    else:
        environment["SPACEWORKS_DEPLOYMENT_PROFILE"] = profile
    result = subprocess.run([sys.executable, "-c", script], cwd=backend,
                            env=environment, capture_output=True, timeout=120, check=False)
    # Do not leak child output: startup errors can include DB/provider credentials.
    assert result.returncode == 0, "fresh full-profile schema/isolation probe failed"
