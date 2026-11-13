"""Deployment removal and import-safe resource report contracts."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("disabled, present", [("events,payments", True), ("bookings", False)])
def test_booking_reports_have_no_events_membership_or_rail_runtime_dependency(disabled, present):
    code = """
import django
from django.core.checks import run_checks
django.setup()
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_subjects import SUBJECTS
from apps.makerspaces.capabilities import FEATURES
keys = {'booking-resource-utilization', 'booking-resource-utilization-pdf', 'booking-reservations', 'booking-answers'}
assert (keys <= REPORT_REGISTRY.keys()) if PRESENT else keys.isdisjoint(REPORT_REGISTRY)
assert ('bookable_space' in SUBJECTS) == PRESENT
assert ('bookings.analytics' in FEATURES) == PRESENT
errors = [(e.id, e.msg, str(e.obj)) for e in run_checks() if e.level >= 40]
assert not errors, errors
""".replace("PRESENT", repr(present))
    from cryptography.fernet import Fernet
    # The isolated runner does not export PII_MASTER_KEY, and a fresh process fails the
    # encryption.E001 deployment check without one; this contract is about tombstoning.
    env = {"PII_MASTER_KEY": Fernet.generate_key().decode(), **os.environ, "TOMBSTONED_APPS": disabled}
    env["PII_MASTER_KEY"] = env["PII_MASTER_KEY"] or Fernet.generate_key().decode()
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2],
                            env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


def test_saved_subject_preferences_import_without_replay_authority():
    from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
    from apps.operations.models_saved_views import SavedView
    # Existing infrastructure deliberately clears the whole state, so numeric
    # source resource IDs cannot resolve to unrelated target resources.
    assert TARGET_FIELD_PROJECTION[(SavedView._meta.label, "state")].resolved_value(SavedView._meta.label, "state") == {}
    assert TARGET_FIELD_PROJECTION[(SavedView._meta.label, "shared")].resolved_value(SavedView._meta.label, "shared") is False


def test_booking_schema_matches_registered_exports_and_typed_allowlists():
    from apps.operations.report_definitions_bookings import ANSWER_FIELDS, RESERVATION_FIELDS
    from apps.operations.serializers_reports_bookings import BookingAnswerReportRowSerializer, BookingReservationReportRowSerializer
    schema = json.loads((Path(__file__).resolve().parents[3] / "frontend/openapi-schema.json").read_text())
    components = schema["components"]["schemas"]
    assert set(components["BookingReservationReportRow"]["properties"]) == set(RESERVATION_FIELDS)
    assert set(components["BookingAnswerReportRow"]["properties"]) == set(ANSWER_FIELDS)
    assert set(BookingReservationReportRowSerializer().fields) == set(RESERVATION_FIELDS)
    assert set(BookingAnswerReportRowSerializer().fields) == set(ANSWER_FIELDS)
    assert "report_features" in components["BookableSpaceAdmin"]["properties"]
    forbidden = {"public_token", "checkin_token", "note", "custom_answers", "member", "payment"}
    assert not forbidden & set(RESERVATION_FIELDS)
    assert not forbidden & set(ANSWER_FIELDS)


@pytest.mark.django_db
def test_account_booking_reports_need_no_membership_or_event_module():
    from apps.operations import reports
    from tests.operations.booking_report_helpers import fixture, booking, filters
    tenant, actor, _, resource, *_ = fixture()
    tenant.enabled_modules = [m for m in tenant.enabled_modules if m not in {"events", "membership", "payments"}]
    tenant.save(update_fields=["enabled_modules"])
    booking(resource)
    for key in ("booking-resource-utilization", "booking-reservations", "booking-answers"):
        assert reports.report_data(key, tenant.pk, actor=actor, report_filters=filters(resource))["typed_rows"]
