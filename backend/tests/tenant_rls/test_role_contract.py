"""A0 role contract and C-25 report-only mode: the app always starts, owner roles only report."""

import subprocess
import sys
from pathlib import Path

import pytest
from django.core.checks import Error, run_checks
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.audit.models import AuditLog
from apps.tenant_rls import role_contract
from apps.tenant_rls.context import tenant_context
from apps.tenant_rls.report import flush
from apps.tenant_rls.role_contract import Contract, decide

from .conftest import labels

pytestmark = pytest.mark.django_db

NARROW = Contract("app", False, False, False)


@pytest.mark.parametrize("contract,mode,expected", [
    (NARROW, "auto", "enforce"),
    (NARROW, "report", "report"),
    (NARROW, "off", "off"),
    (Contract("owner", False, False, True), "auto", "report"),
    (Contract("owner", False, False, True), "enforce", "enforce"),
    (Contract("root", True, False, False), "auto", "inactive"),
    (Contract("rls", False, True, False), "enforce", "inactive"),
    (None, "auto", "inactive"),
])
def test_mode_decision(contract, mode, expected):
    assert decide(contract, mode=mode, probe="") == expected


def test_probe_forces_enforcement_on_a_superuser_run():
    assert decide(Contract("root", True, False, False), mode="auto", probe="probe") == "enforce"
    assert decide(Contract("root", True, False, False), mode="report", probe="probe") == "report"


def test_the_superuser_test_role_is_inactive_and_sends_nothing(boxes, settings):
    settings.TENANT_RLS_PROBE_ROLE = ""
    role_contract.reset_cache()
    assert role_contract.status()["mode"] == "inactive"
    a = boxes[0].makerspace
    with CaptureQueriesContext(connection) as captured, tenant_context(a.pk):
        assert labels() == ["A box", "B box"]
    assert not any("set_config" in query["sql"] for query in captured.captured_queries)


def test_an_owner_role_is_detected_and_downgraded_to_report_only(probe):
    with connection.cursor() as cursor:
        cursor.execute('CREATE ROLE "rls_owner_probe" NOLOGIN NOBYPASSRLS')
        cursor.execute('ALTER TABLE "boxes_box" OWNER TO "rls_owner_probe"')
        cursor.cursor.execute('SET LOCAL ROLE "rls_owner_probe"')
        try:
            contract = role_contract.inspect(connection.connection)
        finally:
            cursor.cursor.execute("SET LOCAL ROLE NONE")
    assert contract.owns_scoped_tables and not contract.superuser
    assert decide(contract, mode="auto", probe="") == "report"


def test_report_only_admits_every_row_and_records_the_violation(probe, boxes, settings):
    settings.TENANT_RLS_MODE = "report"
    role_contract.reset_cache()
    a = boxes[0].makerspace
    with tenant_context(a.pk, label="report-test"):
        assert labels() == ["A box", "B box"]
        flush(label="report-test")
    row = AuditLog.objects.filter(action="rls.report_only_violation").latest("id")
    assert row.meta["table"] == "boxes_box" and row.meta["path"] == "report-test"


def test_checks_never_refuse_start_up(probe, settings):
    settings.TENANT_RLS_PROBE_ROLE = ""
    role_contract.reset_cache()
    messages = [m for m in run_checks(databases=["default"]) if m.id.startswith("tenant_rls")]
    assert messages and all(m.id == "tenant_rls.W002" for m in messages)
    assert not [m for m in messages if isinstance(m, Error)]


def test_off_sends_nothing_even_with_the_probe(probe, boxes, settings):
    settings.TENANT_RLS_MODE = "off"
    role_contract.reset_cache()
    with tenant_context(boxes[0].makerspace.pk):
        assert labels() == ["A box", "B box"]


def test_bundled_runtime_url_refuses_the_owner_as_runtime_role(tmp_path):
    script = Path(__file__).resolve().parents[3] / "scripts" / "bundled-database-url.py"
    env = tmp_path / "static.env"
    env.write_text("POSTGRES_USER=makerspace\nPOSTGRES_APP_USER=makerspace\nPOSTGRES_APP_PASSWORD=x\n")
    refused = subprocess.run([sys.executable, str(script), str(env)], capture_output=True, text=True)
    assert refused.returncode != 0 and "must differ" in refused.stderr
    env.write_text("POSTGRES_APP_PASSWORD=x\n")
    ok = subprocess.run([sys.executable, str(script), str(env)], capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.startswith("postgres://spaceworks_app:")
