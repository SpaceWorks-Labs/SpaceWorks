"""`manage.py account_unification_report`: a dry run that never changes data."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import User

from .ua1_helpers import person, space, staff_row

pytestmark = pytest.mark.django_db


def _report(*args):
    out = StringIO()
    call_command("account_unification_report", *args, stdout=out)
    return out.getvalue()


def test_a_unified_database_has_nothing_to_convert_and_a_stable_digest():
    staff_row(person("already"), space("report"), "event_manager")
    before = User.objects.count()
    plan = json.loads(_report("--format", "json"))
    assert plan["staff_accounts"] == [] and plan["candidate_pairs"] == []
    assert plan["plan_sha256"] == json.loads(_report("--format", "json"))["plan_sha256"]
    assert {"open_pii_windows", "security_locks"} <= set(plan["informational"])
    assert User.objects.count() == before


def test_text_report_lists_security_context():
    from apps.makerspaces.models_security import MakerspaceSecurityLock

    makerspace = space("locked")
    root = User.objects.create_superuser("report-root", "root@example.test", "pw-strong-123")
    MakerspaceSecurityLock.objects.create(makerspace=makerspace, key="security.staff_mfa_required",
                                          floor=True, locked_by=root)
    text = _report()
    assert "Staff accounts to convert: 0" in text
    assert f"Security locks in space {makerspace.pk}: security.staff_mfa_required" in text
    assert "plan_sha256: " in text
