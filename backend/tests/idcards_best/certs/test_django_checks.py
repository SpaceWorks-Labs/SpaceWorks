"""Local: system checks pass and the events models match the migrations."""
from io import StringIO

import pytest
from django.core.checks import run_checks
from django.core.management import call_command

# The isolated runner has no PII master key; that check is environmental.
ENVIRONMENTAL = {"encryption.E001"}


@pytest.mark.django_db
def test_system_checks_pass():
    errors = [item for item in run_checks() if item.is_serious() and item.id not in ENVIRONMENTAL]
    assert errors == []


@pytest.mark.django_db
def test_no_missing_events_migrations():
    out = StringIO()
    try:
        call_command("makemigrations", "events", "--check", "--dry-run", stdout=out)
    except SystemExit as exc:  # pragma: no cover - the failure message is the point
        raise AssertionError(out.getvalue()) from exc
