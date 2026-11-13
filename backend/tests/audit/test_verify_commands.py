"""The two operator verification commands: exact refusals, summaries and failure wording.

``verify_audit_macs`` reads rows in primary-key order and must fail loudly (and specifically) on a
mismatch; ``verify_audit_log`` wraps the integrity verifier and must name where it failed.
"""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.audit.models import AuditBatch, AuditLog
from apps.audit.services import record
from tests.audit_mac_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def _run_macs(**options):
    out = StringIO()
    call_command("verify_audit_macs", stdout=out, **options)
    return out.getvalue()


def _tamper(row, column, value):
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = 'replica'")
        cursor.execute(f"UPDATE audit_auditlog SET {column} = %s WHERE id = %s", [value, row.pk])


class TestVerifyAuditMacsArguments:
    @pytest.mark.parametrize("option", ["start_id", "end_id"])
    @pytest.mark.parametrize("value", [0, -3])
    def test_non_positive_bounds_are_refused(self, option, value):
        flag = "--" + option.replace("_", "-")
        with pytest.raises(CommandError, match=f"{flag} must be positive."):
            _run_macs(**{option: value})

    def test_start_after_end_is_refused(self):
        with pytest.raises(CommandError, match="--start-id must not exceed --end-id."):
            _run_macs(start_id=5, end_id=2)


class TestVerifyAuditMacsOutcome:
    def test_clean_rows_are_reported_as_attested_with_a_success_line(self):
        actor = make_user("vc-clean")
        row = record(actor, "vc.clean", makerspace=make_space("vc-clean"))
        output = _run_macs(start_id=row.pk, end_id=row.pk)
        assert "attested=1 unattested=0 mac_missing=0 mismatch=0 key_unavailable=0" in output
        assert "Verified 1 attested row(s); 0 unattested" in output

    def test_range_limits_which_rows_are_read(self):
        actor = make_user("vc-range")
        space = make_space("vc-range")
        first = record(actor, "vc.first", makerspace=space)
        second = record(actor, "vc.second", makerspace=space)
        assert "attested=1 " in _run_macs(start_id=first.pk, end_id=first.pk)
        assert "attested=1 " in _run_macs(start_id=second.pk, end_id=second.pk)
        assert "attested=2 " in _run_macs(start_id=first.pk, end_id=second.pk)

    def test_a_tampered_row_fails_with_its_id(self):
        actor = make_user("vc-tamper")
        row = record(actor, "vc.before", makerspace=make_space("vc-tamper"))
        _tamper(row, "action", "vc.after")
        with pytest.raises(CommandError, match=rf"Audit MAC mismatch: 1 row\(s\), first at id={row.pk}\."):
            _run_macs(start_id=row.pk, end_id=row.pk)

    def test_a_stripped_mac_above_the_cutover_fails_as_missing(self):
        actor = make_user("vc-stripped")
        row = record(actor, "vc.sealed", makerspace=make_space("vc-stripped"))
        _tamper(row, "row_mac", None)
        with pytest.raises(CommandError, match=rf"1 row\(s\) written after their scope's attestation cutover carry no MAC, first at id={row.pk}\."):
            _run_macs(start_id=row.pk, end_id=row.pk)

    def test_a_mismatch_is_reported_before_a_missing_mac(self):
        actor = make_user("vc-both")
        space = make_space("vc-both")
        bad = record(actor, "vc.bad", makerspace=space)
        stripped = record(actor, "vc.stripped", makerspace=space)
        _tamper(bad, "action", "vc.changed")
        _tamper(stripped, "row_mac", None)
        with pytest.raises(CommandError, match="Audit MAC mismatch: 1 row"):
            _run_macs(start_id=bad.pk, end_id=stripped.pk)


class TestVerifyAuditLog:
    def test_a_clean_log_reports_row_and_batch_counts(self):
        out = StringIO()
        with patch("apps.audit.management.commands.verify_audit_log.verify_audit_integrity", return_value=None):
            call_command("verify_audit_log", stdout=out)
        expected = f"Verified {AuditLog.objects.count()} audit row(s) and {AuditBatch.objects.count()} externally anchored batch(es)."
        assert out.getvalue().strip() == expected

    @pytest.mark.parametrize(
        ("coordinates", "location"),
        [
            ({"makerspace_id": 3, "batch_seq": 9, "audit_log_id": 7}, " (makerspace_id=3, batch_seq=9, audit_log_id=7)"),
            ({"makerspace_id": None, "batch_seq": None, "audit_log_id": 7}, " (audit_log_id=7)"),
            ({"makerspace_id": 3, "batch_seq": None, "audit_log_id": None}, " (makerspace_id=3)"),
            ({"makerspace_id": None, "batch_seq": None, "audit_log_id": None}, ""),
        ],
    )
    def test_a_failure_names_its_class_location_and_detail(self, coordinates, location):
        failure = SimpleNamespace(failure_class=SimpleNamespace(value="row_mac_mismatch"), detail="the detail", **coordinates)
        with patch("apps.audit.management.commands.verify_audit_log.verify_audit_integrity", return_value=failure):
            with pytest.raises(CommandError) as raised:
                call_command("verify_audit_log")
        assert str(raised.value) == f"First audit verification failure: row_mac_mismatch{location}: the detail"
