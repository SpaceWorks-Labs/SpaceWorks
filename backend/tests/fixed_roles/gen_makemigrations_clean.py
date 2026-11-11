"""Not collected by default (no test_ prefix). Throwaway: makemigrations --check
with the conftest's patched ``enabled_modules`` field default restored.

    ./scripts/dev.sh test tests/fixed_roles/gen_makemigrations_clean.py -q
"""

import io
from pathlib import Path

import pytest
from django.core.management import call_command

OUT = Path("/workspace/backend/tests/.junit")


@pytest.mark.django_db
def test_makemigrations_check_with_real_field_default(monkeypatch):
    from apps.makerspaces.models import Makerspace, default_enabled_modules

    field = Makerspace._meta.get_field("enabled_modules")
    lines = [f"patched default under conftest: {field.default!r}"]
    monkeypatch.setattr(field, "default", default_enabled_modules)
    buf = io.StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", "-v", "3", stdout=buf, stderr=buf)
        lines.append("CLEAN")
    except SystemExit:
        lines.append("PENDING")
    lines.append(buf.getvalue())
    OUT.mkdir(exist_ok=True)
    (OUT / "makemigrations_real_default.txt").write_text("\n".join(lines) + "\n")
