from datetime import datetime, timedelta, timezone as utc
from zoneinfo import ZoneInfo

import pytest

from apps.machines import reminders_certifications, reminders_certification_digest
from apps.machines.models import CertificationGrant, MakerspaceMachineTypePolicy
from apps.operations.reminder_sweeper import run_reminder_sweep
from apps.operations.models_reminders import ReminderSchedule
from tests.machines.certification_helpers import _space, _machine_type, _member, _certification
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db(transaction=True)


def world(slug, zone="UTC"):
    space = _space(slug, modules=("machines", "notifications"))
    space.timezone = zone
    space.enabled_features = sorted(set(space.enabled_features) | {"machines.certification_reminders"})
    space.save(update_fields=["timezone", "enabled_features"])
    kind = _machine_type(space)
    _, member = _member(space, slug + "-member")
    cert = _certification(space, kind)
    return space, kind, member, cert


def test_member_and_staff_digest_are_once_per_grant_and_local_day(monkeypatch):
    space, _, member, cert = world("rem-cert", "Asia/Kolkata")
    now = datetime(2026, 10, 11, 18, 40, tzinfo=utc.utc)
    grant = CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=10))
    from apps.integrations.models_contract import NotificationEnvelope
    from tests.machines.certification_helpers import _manager
    _manager(space, "rem-cert-staff", cert.machine_type)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    member_notices = []
    staff_notices = NotificationEnvelope.objects.filter(source_kind="machines.certification_summary")
    monkeypatch.setattr(reminders_certifications, "notify_certification", lambda row, event, **kw: member_notices.append((row.pk, event, kw)))
    run_reminder_sweep(now=now)
    run_reminder_sweep(now=now)
    assert member_notices == [(grant.pk, "expiring", {"include_staff": False})]
    assert staff_notices.count() == 1
    marker = ReminderSchedule.objects.get(source=reminders_certification_digest.SOURCE, makerspace=space)
    assert marker.subject.endswith(":2026-10-12")
    run_reminder_sweep(now=now + timedelta(days=1))
    assert len(member_notices) == 1 and staff_notices.count() == 2


def test_expiry_reminder_uses_local_wall_time_across_dst():
    space, _, member, cert = world("rem-dst", "America/New_York")
    expiry = datetime(2026, 11, 2, 9, tzinfo=ZoneInfo("America/New_York"))
    grant = CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=expiry)
    due = reminders_certifications.reminder_time(space, grant, "expiring")
    assert due.hour == 9 and due.date().isoformat() == "2026-10-19"
    assert expiry.astimezone(utc.utc) - due.astimezone(utc.utc) == timedelta(days=14, hours=1)


def test_revocation_renewal_and_foreign_tenant_suppress_stale_notices(monkeypatch):
    space, _, member, cert = world("rem-stale")
    other, _, _, _ = world("rem-stale-other")
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    grant = CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=7))
    due = reminders_certifications.reminder_time(space, grant, "expiring")
    marker = ReminderSchedule(subject=str(grant.pk), kind="expiring", due_at=due, offset_seconds=0)
    assert reminders_certifications.build(other, marker, now, ZoneInfo("UTC")) is None
    grant.revoked_at = now
    grant.save(update_fields=["revoked_at"])
    assert reminders_certifications.build(space, marker, now, ZoneInfo("UTC")) is None
    grant.revoked_at = None
    grant.save(update_fields=["revoked_at"])
    CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=None)
    assert reminders_certifications.build(space, marker, now, ZoneInfo("UTC")) is None


@pytest.mark.parametrize("module", ["machines", "notifications"])
def test_module_off_prevents_discovery_and_dispatch(module, monkeypatch):
    space, _, member, cert = world("rem-off-" + module)
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=7))
    disable_module(space, module)
    calls = []
    monkeypatch.setattr(reminders_certifications, "notify_certification", lambda *a, **kw: calls.append(a))
    run_reminder_sweep(now=now)
    assert calls == [] and not ReminderSchedule.objects.filter(makerspace=space).exists()


def test_small_batches_progress_past_disabled_policy_and_completed_subjects(monkeypatch):
    space, kind, member, cert = world("rem-batch")
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    MakerspaceMachineTypePolicy.objects.create(makerspace=space, machine_type=kind, cert_reminder_days=0)
    CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=1))
    other_kind = _machine_type(space)
    other_cert = _certification(space, other_kind)
    grant = CertificationGrant.objects.create(certification_type=other_cert, membership=member, expires_at=now + timedelta(days=2))
    seen = []
    monkeypatch.setattr(reminders_certifications, "notify_certification", lambda row, *a, **kw: seen.append(row.pk))
    run_reminder_sweep(now=now, limit=1)
    run_reminder_sweep(now=now, limit=1)
    assert seen == [grant.pk]


def test_short_renewal_does_not_announce_expiry_while_an_older_grant_covers_use():
    space, _, member, cert = world("rem-overlap")
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    original = CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=40))
    CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=2))
    assert list(reminders_certifications.eligible_grants(space).values_list("pk", flat=True)) == [original.pk]
    assert list(reminders_certifications.discover(space, now, 100, ZoneInfo("UTC"))) == []


def test_expired_grant_notice_catches_up_after_downtime_once(monkeypatch):
    space, _, member, cert = world("rem-expired")
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    grant = CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now - timedelta(days=3))
    seen = []
    monkeypatch.setattr(reminders_certifications, "notify_certification", lambda row, event, **kw: seen.append((row.pk, event)))
    run_reminder_sweep(now=now)
    run_reminder_sweep(now=now)
    assert seen == [(grant.pk, "expired")]


def test_reminder_feature_off_keeps_existing_training_records_silent(monkeypatch):
    space, _, member, cert = world("rem-feature-off")
    space.enabled_features = [key for key in space.enabled_features if key != "machines.certification_reminders"]
    space.save(update_fields=["enabled_features"])
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    CertificationGrant.objects.create(certification_type=cert, membership=member, expires_at=now + timedelta(days=7))
    seen = []
    monkeypatch.setattr(reminders_certifications, "notify_certification", lambda *a, **kw: seen.append(a))
    run_reminder_sweep(now=now)
    assert seen == [] and not ReminderSchedule.objects.filter(makerspace=space).exists()


def test_switch_off_refuses_existing_expiry_and_staff_digest(monkeypatch):
    from django.utils import timezone

    from apps.integrations.email_preferences import blocked_reason
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_catalog_sources import event_live
    from apps.integrations.notification_sources import source_eligible
    from apps.machines import notifications_p2_certifications as notifications
    from tests.machines.certification_helpers import _manager

    space, kind, member, cert = world("rem-queued-off")
    now = datetime(2026, 10, 11, 10, tzinfo=utc.utc)
    monkeypatch.setattr(timezone, "now", lambda: now)
    grant = CertificationGrant.objects.create(certification_type=cert, membership=member,
                                               expires_at=now + timedelta(days=7))
    staff, _ = _manager(space, "rem-queued-staff", kind)
    member_notice = NotificationEnvelope.objects.create(makerspace=space, recipient=member.user,
        feature="certifications", stream="certifications", event="expiring", audience="requester",
        source_kind=notifications.KIND, source_id=str(grant.pk), revision=notifications.version(grant),
        dedup_key="reminder-switch:member")
    staff_notice = NotificationEnvelope.objects.create(makerspace=space, recipient=staff,
        feature="certifications", stream="certifications", event="expiring", audience="staff",
        source_kind=notifications.DIGEST, source_id=str(cert.pk), context={"day": now.date().isoformat()},
        scope={"machine_type_id": kind.pk}, dedup_key="reminder-switch:staff")
    assert source_eligible(member_notice) and source_eligible(staff_notice)

    space.enabled_features.remove("machines.certification_reminders")
    space.save(update_fields=["enabled_features"])

    for row in (member_notice, staff_notice):
        row.refresh_from_db()
        assert not source_eligible(row)
    for event in ("expiring", "expired"):
        assert blocked_reason(space, "member@example.test", feature="certifications", event=event) == (
            "notification_source_disabled"
        )
    assert all(event_live(space, "certifications", event) for event in ("granted", "revoked"))

    space.enabled_features.remove("machines.certifications")
    space.enabled_features.append("machines.certification_reminders")
    space.save(update_fields=["enabled_features"])
    assert not event_live(space, "certifications", "expiring")

# Decision 319 (retired feature): kept, not deleted -- the cases document the pre-319 behaviour.
_RETIRED = __import__("pytest").mark.skip(reason="Decision 319: certifications, trainings and inductions are retired as a gate and as a feature; replaced by tests/parity_0120/machine_access.")
_existing = globals().get("pytestmark", [])
pytestmark = [*(_existing if isinstance(_existing, (list, tuple)) else [_existing]), _RETIRED]
