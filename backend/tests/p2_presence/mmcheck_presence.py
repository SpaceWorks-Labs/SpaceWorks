"""Throwaway (not collected by default): makemigrations --check for the presence lane."""
import io
import os

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_makemigrations_check_presence(monkeypatch):
    # tests/conftest.py autouse-patches the enabled_modules FIELD default to a lambda;
    # restore the real callable or the autodetector reports a phantom makerspaces change.
    from apps.makerspaces.models import Makerspace, default_enabled_modules
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_modules"), "default", default_enabled_modules)
    out = io.StringIO()
    code = 0
    try:
        call_command("makemigrations", "presence", "--check", "--dry-run", "-v", "3", stdout=out, stderr=out)
    except SystemExit as exc:
        code = exc.code
    full = io.StringIO()
    try:
        call_command("makemigrations", "--dry-run", stdout=full, stderr=full)
    except SystemExit:
        pass
    os.makedirs("/workspace/backend/tests/.junit", exist_ok=True)
    with open("/workspace/backend/tests/.junit/p2-presence-makemigrations.txt", "w") as fh:
        fh.write(f"presence exit={code}\n{out.getvalue()}\n--- all apps dry-run ---\n{full.getvalue()}")
    assert code in (0, None), out.getvalue()
