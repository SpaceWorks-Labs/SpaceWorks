from datetime import timedelta

import pytest
from django.http import Http404
from django.utils import timezone

from apps.hosting_requests import retention, workflow
from apps.hosting_requests.models import HostingRequest
from apps.hosting_requests.notifications import SOURCE_KIND
from apps.integrations.models import EmailLog
from tests.hosting_requests.helpers import invited_row, public_row, space

pytestmark = pytest.mark.django_db
S = HostingRequest.Status


def ago(**delta):
    return timezone.now() - timedelta(**delta)


def mail_log(row):
    return EmailLog.objects.create(
        makerspace=None, to_email=row.applicant_email or "x@example.test", subject="Hosting",
        stream="governance", event="hosting_request_verify", audience="applicant",
        connection_kind="platform", source_kind=SOURCE_KIND, source_id=row.pk,
    )


def test_deletes_only_expired_unverified_public_rows_and_their_mail_logs(managed):
    expired, _ = public_row(status=S.PENDING_VERIFICATION, verification_expires_at=ago(minutes=1))
    fresh, _ = public_row(status=S.PENDING_VERIFICATION, verification_expires_at=ago(minutes=-60))
    invited, _ = invited_row(
        makerspace=space("retention-inviter"), status=S.PENDING_VERIFICATION,
        verification_expires_at=ago(minutes=1),
    )
    submitted, _ = public_row(verification_expires_at=ago(days=5))
    log = mail_log(expired)
    kept_log = mail_log(fresh)

    assert retention.sweep()["deleted"] == 1
    assert not HostingRequest.objects.filter(pk=expired.pk).exists()
    assert not EmailLog.objects.filter(pk=log.pk).exists()
    assert set(HostingRequest.objects.values_list("pk", flat=True)) == {fresh.pk, invited.pk, submitted.pk}
    assert EmailLog.objects.filter(pk=kept_log.pk).exists()


def test_redacts_rejected_and_withdrawn_rows_after_ninety_days_not_eighty_nine(managed):
    old_rejected, raw = public_row(status=S.REJECTED, decided_at=ago(days=90, minutes=1))
    young_rejected, _ = public_row(status=S.REJECTED, decided_at=ago(days=89))
    old_withdrawn, _ = invited_row(
        makerspace=space("retention-withdrawn"), status=S.WITHDRAWN, withdrawn_at=ago(days=91),
    )
    log = mail_log(old_rejected)

    assert retention.sweep()["redacted"] == 2
    old_rejected.refresh_from_db()
    young_rejected.refresh_from_db()
    old_withdrawn.refresh_from_db()
    for row in (old_rejected, old_withdrawn):
        assert row.redacted_at is not None
        assert (row.applicant_name, row.applicant_email, row.applicant_phone, row.description,
                row.space_website_url, row.invite_note, row.new_organization_name) == ("",) * 7
        assert row.invite_token_digest is None and row.access_token_digest is None
    # The decision record survives.
    assert old_rejected.space_name == "Row Space" and old_rejected.location == "Somewhere"
    assert old_rejected.rejection_reason == "Not a fit for this platform."
    assert old_rejected.status == S.REJECTED and old_rejected.decided_at is not None
    assert young_rejected.redacted_at is None and young_rejected.applicant_email
    # No mail log keeps the applicant's address, and the status link is dead.
    assert not EmailLog.objects.filter(pk=log.pk).exists()
    assert not EmailLog.objects.filter(source_kind=SOURCE_KIND, source_id=old_rejected.pk).exists()
    with pytest.raises(Http404):
        workflow.open_by_token(raw)


def test_redacts_dead_invitations_ninety_days_after_invite_expiry(managed):
    makerspace = space("retention-invites")
    dead, _ = invited_row(makerspace=makerspace, invite_expires_at=ago(days=91))
    dead_pending, _ = invited_row(
        makerspace=makerspace, status=S.PENDING_VERIFICATION, invite_expires_at=ago(days=95),
    )
    recent, _ = invited_row(makerspace=makerspace, invite_expires_at=ago(days=10))
    assert retention.sweep()["redacted"] == 2
    for row in (dead, dead_pending):
        row.refresh_from_db()
        assert row.redacted_at is not None and row.applicant_email == ""
    recent.refresh_from_db()
    assert recent.redacted_at is None


def test_accepted_rows_are_kept_whole(managed):
    accepted, _ = public_row(status=S.ACCEPTED, decided_at=ago(days=400))
    assert retention.sweep() == {"deleted": 0, "redacted": 0}
    accepted.refresh_from_db()
    assert accepted.redacted_at is None and accepted.applicant_email == "ada@example.test"


def test_each_run_is_bounded(managed, monkeypatch):
    monkeypatch.setattr(retention, "BATCH", 2)
    monkeypatch.setattr(retention, "MAX_LOOPS", 2)
    for _ in range(5):
        public_row(status=S.PENDING_VERIFICATION, verification_expires_at=ago(hours=1))
    assert retention.sweep()["deleted"] == 4
    assert HostingRequest.objects.count() == 1
    assert retention.sweep()["deleted"] == 1


def test_sweep_runs_when_the_feature_is_not_available(self_host):
    row, _ = public_row(status=S.REJECTED, decided_at=ago(days=120))
    assert retention.sweep()["redacted"] == 1
    row.refresh_from_db()
    assert row.redacted_at is not None


def test_task_is_in_both_schedulers(settings):
    from apps.hosting_requests.tasks import sweep_hosting_requests_task
    from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS

    name = "apps.hosting_requests.tasks.sweep_hosting_requests_task"
    assert sweep_hosting_requests_task.name == name
    assert settings.CELERY_BEAT_SCHEDULE["hosting-request-retention"]["task"] == name
    assert ("hosting-request-retention", name, 24 * 60) in SCHEDULED_TASKS
    assert sweep_hosting_requests_task.delay().get() == {"deleted": 0, "redacted": 0}
