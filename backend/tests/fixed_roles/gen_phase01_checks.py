"""Not collected by default (no test_ prefix). Integration verification helpers:

    ./scripts/dev.sh test tests/fixed_roles/gen_phase01_checks.py -q -s

Writes the merged-graph catalog digest and the makemigrations --check output to
tests/.junit/, and regenerates the OpenAPI snapshot.
"""

import io
from pathlib import Path

import pytest
from django.core.management import call_command

OUT = Path("/workspace/backend/tests/.junit")


@pytest.mark.django_db
def test_write_catalog_digest():
    from apps.tenant_migration.tenant_dump_catalog import schema_digest

    OUT.mkdir(exist_ok=True)
    (OUT / "catalog_digest.txt").write_text(schema_digest() + "\n")


@pytest.mark.django_db
def test_makemigrations_check():
    buf = io.StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", "-v", "3", stdout=buf, stderr=buf)
        status = "CLEAN"
    except SystemExit:
        status = "PENDING"
    detail = io.StringIO()
    call_command("makemigrations", "makerspaces", "--dry-run", "-v", "3", stdout=detail, stderr=detail)
    (OUT / "makemigrations.txt").write_text(status + "\n" + buf.getvalue() + "\n--- detail\n" + detail.getvalue())


@pytest.mark.django_db
def test_regenerate_openapi_snapshot():
    call_command(
        "spectacular", "--format", "openapi-json",
        "--file", "/workspace/frontend/openapi-schema.json",
    )
