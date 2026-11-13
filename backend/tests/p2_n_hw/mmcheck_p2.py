import io
import os

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_makemigrations_check():
    out = io.StringIO()
    os.makedirs("/workspace/backend/tests/.junit", exist_ok=True)
    try:
        call_command("makemigrations", "inventory", "--check", "--dry-run", stdout=out, stderr=out)
        status = "clean"
    except SystemExit as exc:
        status = f"changes ({exc.code})"
    with open("/workspace/backend/tests/.junit/mm-n-hw.txt", "w") as handle:
        handle.write(status + "\n" + out.getvalue())
    assert status == "clean", out.getvalue()
