"""Local helper (never committed): regenerate the OpenAPI snapshot inside the test container."""

from pathlib import Path

from django.core.management import call_command


def test_regenerate_openapi_snapshot():
    target = Path(__file__).resolve().parents[3] / "frontend" / "openapi-schema.json"
    call_command("spectacular", "--format", "openapi-json", "--file", str(target))
    assert target.stat().st_size > 1000
