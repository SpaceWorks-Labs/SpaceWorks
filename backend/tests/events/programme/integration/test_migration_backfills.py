"""Exercise the historical graph, including a real reverse/reapply cycle."""
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BASE = [("events", "0036_event_speakers")]
FINAL = [("events", "0044_events_programme_guards")]


def migrate(target):
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    refreshed = MigrationExecutor(connection)
    return refreshed.loader.project_state(list(refreshed.loader.applied_migrations)).apps


@pytest.mark.django_db(transaction=True)
def test_legacy_subject_manual_grant_and_qr_survive_forward_reverse_forward():
    # Later migrations (and other apps' migrations depending on them) are unapplied by
    # the reverse; restore the full graph so later transactional tests see every column.
    latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
    old = migrate(BASE)
    try:
        space = old.get_model("makerspaces", "Makerspace").objects.create(name="Legacy", slug="gf1-legacy")
        old.get_model("encryption", "PiiMakerspaceWriteFence").objects.get_or_create(makerspace_id=space.pk)
        user = old.get_model("accounts", "User").objects.create(username="gf1-member", account_kind="member")
        # A staff account needs exactly one seeded-role membership (DB trigger); historical
        # app state cannot seed roles, and the grant only needs a distinct issuer row.
        issuer = old.get_model("accounts", "User").objects.create(username="gf1-issuer", account_kind="member")
        now = timezone.now()
        event = old.get_model("events", "Event").objects.create(makerspace_id=space.pk, title="Legacy event",
            starts_at=now, ends_at=now + timedelta(hours=2), timezone_name="Asia/Kolkata")
        registration = old.get_model("events", "EventRegistration").objects.create(event_id=event.pk,
            member_id=user.pk, name="Legacy member", email="member@example.test", status="attended")
        survey = old.get_model("events", "EventFeedbackSurvey").objects.create(event_id=event.pk, title="Feedback")
        response = old.get_model("events", "EventFeedbackResponse").objects.create(survey_id=survey.pk,
            registration_id=registration.pk, answers_snapshot="{}", certificate_requested=True)
        certificate = old.get_model("events", "EventAttendanceCertificate").objects.create(
            response_id=response.pk, registration_id=registration.pk, revision=1, recipient_name="Legacy member",
            event_title=event.title, event_starts_at=event.starts_at, event_ends_at=event.ends_at,
            issuer_name="Legacy", object_key="event-certificates/legacy.pdf")
        grant = old.get_model("events", "EventStaffGrant").objects.create(makerspace_id=space.pk,
            event_id=event.pk, user_id=user.pk, granted_by_id=issuer.pk, permissions=["check_in"])

        def verify(current):
            row = current.get_model("events", "EventAttendanceCertificate").objects.get(pk=certificate.pk)
            assert (row.event_id, row.recipient_member_id, row.kind, row.event_timezone_name) == (
                event.pk, user.pk, "attendance", "Asia/Kolkata")
            restored = current.get_model("events", "EventRegistration").objects.get(pk=registration.pk)
            assert restored.credential_mode == "legacy"
            assert restored.checkin_token == registration.checkin_token
            entitlement = current.get_model("events", "EventGrantEntitlement").objects.get(grant_id=grant.pk)
            assert entitlement.source_kind == "manual" and entitlement.permissions == ["check_in"]

        verify(migrate(FINAL))
        migrate(BASE)
        verify(migrate(FINAL))
    finally:
        migrate(latest)
