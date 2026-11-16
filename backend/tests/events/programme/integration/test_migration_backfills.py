"""Exercise the programme backfill forward/reverse/forward in isolated historical tables."""
from datetime import timedelta
from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.state import ProjectState
from django.utils import timezone

from tests.account_split.test_p1_data_migration import historical_tables


@pytest.mark.django_db(transaction=True)
def test_legacy_subject_manual_grant_and_qr_survive_forward_reverse_forward():
    labels = ["makerspaces.Makerspace", "accounts.User", *["events." + name for name in (
        "Event", "EventRegistration", "EventFeedbackSurvey", "EventFeedbackResponse",
        "EventAttendanceCertificate", "EventStaffGrant", "EventGrantEntitlement",
        "EventCertificateArtwork", "EventBroadcast", "HackathonPrize", "EventRoleAssignment",
        "EventResultRevision", "EventBroadcastPreview")]]
    with historical_tables([("events", "0042_events_programme_schema")], labels) as old:
        space = old.get_model("makerspaces", "Makerspace").objects.create(name="Legacy", slug="gf1-legacy")
        user = old.get_model("accounts", "User").objects.create(username="gf1-member")
        # A staff account needs exactly one seeded-role membership (DB trigger); historical
        # app state cannot seed roles, and the grant only needs a distinct issuer row.
        issuer = old.get_model("accounts", "User").objects.create(username="gf1-issuer")
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

        module = import_module("apps.events.migrations.0043_events_programme_backfills")
        step = module.Migration("0043_events_programme_backfills", "events")
        original = ProjectState.from_apps(old)
        # 0043 adds these FKs; its real dependency 0042 already creates the targets.
        # Include them in this reduced fixture instead of changing the product graph.
        assert ("events", "0042_events_programme_schema") in step.dependencies
        for name in ("hackathonprize", "eventroleassignment", "eventresultrevision", "eventbroadcastpreview"):
            assert ("events", name) in original.models
        # Install the real pre-programme artwork guard used by the data step.
        artwork_sql = import_module("apps.events.migrations.0030_certificate_templates").REVISION_GUARD
        start = artwork_sql.index("CREATE FUNCTION events_guard_artwork")
        end = artwork_sql.index("CREATE FUNCTION events_guard_layout_snapshot")
        with connection.cursor() as cursor:
            cursor.execute(artwork_sql[start:end])
        with connection.schema_editor() as editor:
            current = step.apply(original.clone(), editor)
        verify(current.apps)
        with connection.schema_editor() as editor:
            step.unapply(original.clone(), editor)
        with connection.schema_editor() as editor:
            current = step.apply(original.clone(), editor)
        verify(current.apps)
