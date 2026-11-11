import io

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_hosting_requests_has_no_pending_migration():
    out = io.StringIO()
    try:
        call_command("makemigrations", "hosting_requests", "--check", "--dry-run", "-v", "3",
                     stdout=out, stderr=out)
    except SystemExit:
        pytest.fail(out.getvalue())


@pytest.mark.django_db
def test_system_checks_pass(settings):
    from cryptography.fernet import Fernet
    # The isolated runner exports no PII_MASTER_KEY; encryption.E001 is a deployment check.
    settings.PII_MASTER_KEY = settings.PII_MASTER_KEY or Fernet.generate_key().decode()
    call_command("check", "--fail-level", "ERROR")
