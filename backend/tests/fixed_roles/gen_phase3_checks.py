"""Not collected by default (no test_ prefix). Phase 3 integration artifacts:

    ./scripts/dev.sh test tests/fixed_roles/gen_phase3_checks.py -q -p no:randomly

Writes the merged-graph catalog digest and the makemigrations --check result to tests/.junit/, and
regenerates the OpenAPI snapshot. The autouse conftest fixture swaps Makerspace.enabled_modules' default for
a lambda; the migration check restores the real callable first, or it reports a false AlterField.
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
def test_makemigrations_check(monkeypatch):
    from apps.makerspaces.models import Makerspace, default_enabled_modules

    monkeypatch.setattr(Makerspace._meta.get_field("enabled_modules"), "default", default_enabled_modules)
    buf = io.StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", "-v", "3", stdout=buf, stderr=buf)
        status = "CLEAN"
    except SystemExit:
        status = "PENDING"
    OUT.mkdir(exist_ok=True)
    (OUT / "makemigrations.txt").write_text(status + "\n" + buf.getvalue())


@pytest.mark.django_db
def test_regenerate_openapi_snapshot():
    call_command(
        "spectacular", "--format", "openapi-json",
        "--file", "/workspace/frontend/openapi-schema.json",
    )
