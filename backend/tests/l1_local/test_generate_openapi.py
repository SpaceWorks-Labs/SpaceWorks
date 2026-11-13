"""Local helper (never committed): regenerate the OpenAPI snapshot inside the test container."""

import os
from pathlib import Path

import pytest
from django.core.management import call_command


def test_regenerate_openapi_snapshot():
    target = Path(__file__).resolve().parents[3] / "frontend" / "openapi-schema.json"
    if not os.access(target, os.W_OK):  # CI mounts the checkout read-only; this is a local regeneration helper
        pytest.skip("openapi snapshot is not writable here (read-only checkout)")
    call_command("spectacular", "--format", "openapi-json", "--file", str(target))
    assert target.stat().st_size > 1000
