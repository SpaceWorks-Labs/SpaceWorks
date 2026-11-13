"""Local helpers (never committed): migrations check and OpenAPI snapshot regeneration in the container."""
import os
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_makemigrations_check(monkeypatch):
    # tests/conftest.py swaps both Makerspace JSONField defaults for lambdas in every test;
    # put the real callables back so the autodetector sees the production model state.
    from apps.makerspaces.capabilities import default_enabled_features
    from apps.makerspaces.models import Makerspace, default_enabled_modules
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_modules"), "default", default_enabled_modules)
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_features"), "default", default_enabled_features)
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", "-v", "3", stdout=out)
    except SystemExit:
        pytest.fail("pending model changes:\n" + out.getvalue())
    assert "No changes detected" in out.getvalue()


def test_regenerate_openapi_snapshot():
    target = Path(__file__).resolve().parents[3] / "frontend" / "openapi-schema.json"
    if not os.access(target, os.W_OK):  # CI mounts the checkout read-only; this is a local regeneration helper
        pytest.skip("openapi snapshot is not writable here (read-only checkout)")
    call_command("spectacular", "--format", "openapi-json", "--file", str(target))
    assert target.stat().st_size > 1000
