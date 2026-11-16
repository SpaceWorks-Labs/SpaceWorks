"""Local helper (never committed): regenerate the OpenAPI schema into pytest temporary storage."""

from django.core.management import call_command


def test_regenerate_openapi_snapshot(tmp_path):
    target = tmp_path / "openapi-schema.json"
    call_command("spectacular", "--format", "openapi-json", "--file", str(target))
    assert target.stat().st_size > 1000
