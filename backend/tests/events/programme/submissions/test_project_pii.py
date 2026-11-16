"""The real mapper stores envelopes while domain readers retain dictionary APIs."""
import json
from unittest.mock import Mock

import pytest
from django.db import connection, transaction, DatabaseError

from apps.encryption.crypto import is_envelope
from apps.encryption.services import get_or_create_active_dek
from apps.events.hackathons.team_models import HackathonTeam, HackathonTeamMember
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot, SubmissionIntegrityFlag
from apps.events.submissions.pii import prepare_documents
from tests.encryption.conftest import enabled_encryption
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def team_for(event, user):
    with transaction.atomic():
        application = HackathonApplication.objects.create(event=event, member=user)
        team = HackathonTeam.objects.create(event=event, leader=user, name="Private makers")
        HackathonTeamMember.objects.create(event=event, team=team, member=user, application=application,
            creator=user, state="active")
    return team


def test_project_and_frozen_answers_are_ciphertext_without_broker_io_under_locks(monkeypatch):
    user = account("private-project")
    event = open_event(event_space("private-project"))
    team = team_for(event, user)
    answers = {"emergency": {"name": "Private Contact", "phone": "+15550123456"}}
    with enabled_encryption():
        get_or_create_active_dek(event.makerspace_id)
        with prepare_documents(event.pk):
            forbidden = Mock(side_effect=AssertionError("Broker/provisioning under event locks"))
            monkeypatch.setattr("apps.encryption.mappers.get_or_create_active_dek", forbidden)
            with transaction.atomic():
                project = HackathonSubmission.objects.create(event=event, team=team, form_answers=answers,
                    triage_reason="Private review explanation")
                snapshot = SubmissionSnapshot.objects.create(submission=project, sequence=1, submitted_by=user,
                    project={"title": "Public title", "form_answers": answers}, content_sha256="a" * 64,
                    amendment_reason="Private amendment explanation")
                flag = SubmissionIntegrityFlag.objects.create(snapshot=snapshot, rule_key="test", reason="Private flag reason")
            forbidden.assert_not_called()
        for model, name, pk in ((HackathonSubmission, "form_answers", project.pk),
                                (SubmissionSnapshot, "project", snapshot.pk),
                                (HackathonSubmission, "triage_reason", project.pk),
                                (SubmissionSnapshot, "amendment_reason", snapshot.pk),
                                (SubmissionIntegrityFlag, "reason", flag.pk)):
            raw = model.objects.values_list(name, flat=True).get(pk=pk)
            assert is_envelope(raw) and "Private Contact" not in raw
        assert HackathonSubmission.objects.get(pk=project.pk).form_answers == answers
        assert SubmissionSnapshot.objects.get(pk=snapshot.pk).project["form_answers"] == answers
        with prepare_documents(event.pk), transaction.atomic():
            changed = HackathonSubmission.objects.get(pk=project.pk)
            assert changed.form_answers == answers
            changed.form_answers = {"new": "Replacement"}
            changed.save(update_fields=["form_answers"])
        assert HackathonSubmission.objects.get(pk=project.pk).form_answers == {"new": "Replacement"}
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE events_submissionsnapshot SET project=%s WHERE id=%s",
                           [json.dumps({"tampered": True}), snapshot.pk])


def test_missing_preparation_cannot_store_plaintext():
    user = account("no-project-key")
    event = open_event(event_space("no-project-key"))
    team = team_for(event, user)
    with enabled_encryption(), pytest.raises(Exception) as caught:
        HackathonSubmission.objects.create(event=event, team=team, form_answers={"private": "value"})
    assert "pii_preparation_required" in str(caught.value.detail)
    assert not HackathonSubmission.objects.filter(event=event).exists()
