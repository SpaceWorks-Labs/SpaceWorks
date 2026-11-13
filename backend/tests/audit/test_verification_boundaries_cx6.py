"""Verification limits at equality, immutable filters and terminal replay cases."""
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.audit import services as audit, verification_runs as runs
from apps.audit.models import AuditLog, AuditVerificationRun, AuditVerificationRunEvent
from apps.audit.verification_execution import execute_attempt, fail_attempt
from apps.makerspaces.models import Makerspace
from tests.accounts.ua1_helpers import platform

State = AuditVerificationRunEvent.State


@pytest.mark.parametrize("profile,limits", [("full", (10000, 50000, 2500, 256, 2760)),
                                           ("free", (250, 1000, 25, 8, 36))])
@pytest.mark.parametrize("dimension", range(5))
def test_every_work_bound_accepts_equality_and_refuses_one_over(settings, profile, limits, dimension):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = profile
    assert runs.check_bounds(limits) is None
    excessive = list(limits)
    excessive[dimension] += 1
    expected = runs.NarrowAuditRange if dimension == 0 else runs.VerificationScopeTooLarge
    with pytest.raises(expected) as error:
        runs.check_bounds(excessive)
    assert error.value.status_code == 400
    assert error.value.code == ("narrow_audit_range" if dimension == 0 else "audit_verification_scope_too_large")


@pytest.mark.django_db
@pytest.mark.parametrize("dimension", ["tenant", "actor", "action", "target_type", "target_id", "start", "end"])
def test_run_filters_apply_the_snapshot_tenant_actor_target_and_half_open_time_range(monkeypatch, dimension):
    home = Makerspace.objects.create(name="Verification home", slug="cx6-verification-home")
    away = Makerspace.objects.create(name="Verification away", slug="cx6-verification-away")
    actor = platform("cx6-verification-root")
    other_actor = platform("cx6-verification-other-root")
    at = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: at)
    values = {"makerspace": home, "actor": actor, "action": "cx6.selected",
              "target_type": "makerspaces.makerspace", "target_id": str(home.pk),
              "created_at": timezone.now()}
    selected = AuditLog.objects.create(**values)
    difference = {
        "tenant": {"makerspace": away}, "actor": {"actor": other_actor},
        "action": {"action": "cx6.other"}, "target_type": {"target_type": "accounts.user"},
        "target_id": {"target_id": str(away.pk)},
        "start": {"created_at": at - timedelta(microseconds=1)},
        "end": {"created_at": at + timedelta(seconds=1)},
    }[dimension]
    if dimension in {"start", "end"}:
        monkeypatch.setattr(timezone, "now", lambda observed_at=difference["created_at"]: observed_at)
        difference = {"created_at": timezone.now()}
    # Insert each sentinel once, never UPDATE an immutable audit timestamp.
    sentinel = AuditLog.objects.create(**{**values, **difference})
    snapshot = sentinel.pk
    filters = runs.normalized_filters({"action": "cx6.selected", "actor": actor.pk,
        "target_type": "makerspaces.makerspace", "target_id": str(home.pk),
        "start": at, "end": at + timedelta(seconds=1)})
    assert selected.pk <= snapshot and sentinel.pk <= snapshot
    assert list(runs.run_rows(home.pk, filters, snapshot).values_list("pk", flat=True)) == [selected.pk]
    filters["end_at"] = selected.created_at
    assert list(runs.run_rows(home.pk, filters, snapshot)) == []
    assert runs.fingerprint(home.pk, filters) == runs.fingerprint(home.pk, dict(reversed(list(filters.items()))))
    assert runs.fingerprint(home.pk, filters) != runs.fingerprint(away.pk, filters)


@pytest.mark.django_db
def test_snapshot_excludes_an_otherwise_matching_row_created_after_admission(monkeypatch):
    home = Makerspace.objects.create(name="Snapshot home", slug="cx6-snapshot-home")
    actor = platform("cx6-snapshot-root")
    at = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: at)
    values = {"makerspace": home, "actor": actor, "action": "cx6.snapshot", "created_at": timezone.now()}
    selected = AuditLog.objects.create(**values)
    later = AuditLog.objects.create(**values)
    filters = runs.normalized_filters({"action": "cx6.snapshot"})
    assert later.pk > selected.pk
    assert list(runs.run_rows(home.pk, filters, selected.pk).values_list("pk", flat=True)) == [selected.pk]
    assert list(runs.run_rows(home.pk, filters).order_by("pk").values_list("pk", flat=True)) == [selected.pk, later.pk]


@pytest.mark.django_db
def test_root_without_an_event_and_a_missing_failure_target_are_noops():
    space = Makerspace.objects.create(name="Empty run", slug="cx6-empty-run")
    run = AuditVerificationRun.objects.create(makerspace=space, snapshot_max_id=0, filter_fingerprint="a" * 64)
    assert execute_attempt(run.pk) is None
    assert fail_attempt(987654321, "task_error") is None
    assert fail_attempt(run.pk, "task_error") is None
    assert run.events.count() == 0
    assert AuditLog.objects.filter(action="audit.verification_finished", target_id=str(run.pk)).count() == 0


@pytest.mark.django_db
def test_missing_master_key_makes_the_real_attempt_incomplete_without_retry(settings):
    settings.AUDIT_ATTESTATION_ANCHOR_BACKEND = ""
    space = Makerspace.objects.create(name="Unavailable key", slug="cx6-unavailable-key")
    root = platform("cx6-unavailable-root")
    row = audit.record(root, "cx6.attested", makerspace=space)
    assert row.row_mac is not None
    run = AuditVerificationRun.objects.create(makerspace=space, requested_by=root,
        snapshot_max_id=row.pk, filter_fingerprint="a" * 64, action_filter="cx6.attested")
    runs.append_event(run, State.QUEUED, 0)
    settings.AUDIT_MAC_MASTER_KEY = ""
    event = execute_attempt(run.pk)
    assert (event.state, event.attempt, event.failure_code) == (State.INCOMPLETE, 1, "verification_unavailable")
    assert (event.row_count, event.mac_unavailable_count, event.unbatched_count) == (1, 1, 1)
    assert list(run.events.order_by("pk").values_list("state", flat=True)) == [State.QUEUED, State.RUNNING, State.INCOMPLETE]
    assert execute_attempt(run.pk) is None
    assert AuditLog.objects.filter(action="audit.verification_finished", target_id=str(run.pk)).count() == 1
