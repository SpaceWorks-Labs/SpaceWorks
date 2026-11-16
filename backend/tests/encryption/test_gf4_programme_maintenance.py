"""Real trigger and command coverage for immutable programme representation rewrites."""
import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.encryption.crypto import is_envelope
from apps.encryption.maintenance import write_legacy_values
from apps.encryption.preparation import prepare_tenants
from apps.encryption.write_fence import close_global, close_makerspace, fence_operation, reopen
from apps.events.models import Event
from apps.events.judging.models_scoring import JudgeAssignment, JudgeScore, JudgingReason
from apps.events.judging.models_definitions import JudgingRound
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.hackathons.team_models import HackathonTeam
from apps.events.submissions.models_projects import HackathonSubmission, SubmissionSnapshot
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption
from tests.events.programme.answer_derivations.conftest import age_world, create_subject, prepare, insert
from apps.events.contracts.subjects import SubjectKind

pytestmark = pytest.mark.django_db(transaction=True)


def world():
    actor = User.objects.create_superuser(username="immutable-pii-operator")
    tenant = Makerspace.objects.create(name="Immutable PII", slug="immutable-pii")
    event = Event.objects.create(makerspace=tenant, title="History", starts_at=timezone.now(),
        ends_at=timezone.now()+timedelta(hours=1))
    return actor, tenant, event


def raw(row, field):
    return type(row).objects.values_list(field, flat=True).get(pk=row.pk)


def test_history_backfill_and_rollback_preserve_every_nonmapped_column():
    actor, tenant, event = world()
    row = JudgingReason.objects.create(makerspace=tenant, event=event, actor=actor, body="Private reason")
    before = JudgingReason.objects.values().get(pk=row.pk)
    with enabled_encryption():
        operation = close_global("enable_transition", actor.pk, all_makerspaces=True)
        try:
            call_command("backfill_scoped_pii", makerspace=tenant.pk, model="events.JudgingReason",
                fence_operation=operation)
            assert is_envelope(raw(row, "body"))
            after = JudgingReason.objects.values().get(pk=row.pk)
            assert {k:v for k,v in before.items() if k!="body"} == {k:v for k,v in after.items() if k!="body"}
            with pytest.raises(DatabaseError), transaction.atomic(), fence_operation(operation):
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE events_judgingreason SET created_at=created_at+interval '1 second' WHERE id=%s", [row.pk])
        finally:
            reopen(operation, actor.pk)
        operation = close_global("decrypt_rollback", actor.pk, all_makerspaces=True)
        try:
            call_command("decrypt_scoped_pii", makerspace=tenant.pk, model="events.JudgingReason",
                actor_id=actor.pk, confirm_makerspace=tenant.pk, fence_operation=str(operation))
            assert JudgingReason.objects.values().get(pk=row.pk) == before
        finally:
            reopen(operation, actor.pk)


def test_single_closed_tenant_is_insufficient_for_history_maintenance():
    actor, tenant, event = world()
    row = JudgingReason.objects.create(makerspace=tenant, event=event, actor=actor, body="Private reason")
    with enabled_encryption(), prepare_tenants([tenant.pk]):
        operation = close_makerspace(tenant.pk, "decrypt_rollback", actor.pk)
        try:
            with transaction.atomic(), fence_operation(operation), pytest.raises(ValidationError):
                write_legacy_values(row, {"body": "altered"})
            assert raw(row, "body") == "Private reason"
        finally:
            reopen(operation, actor.pk)


def test_submitted_score_backfill_changes_only_notes_and_still_refuses_rescoring():
    actor, tenant, event = world()
    # Programme rows require member identities (DB guards); the platform operator only
    # runs the maintenance commands. An active team holds its leader as a member.
    from apps.events.hackathons.admission_models import HackathonApplication
    from apps.events.hackathons.team_models import HackathonTeamMember
    member = User.objects.create_user(username="score-member", account_kind="member")
    judge = User.objects.create_user(username="score-judge", account_kind="member")
    with transaction.atomic():
        application = HackathonApplication.objects.create(event=event, member=member)
        team = HackathonTeam.objects.create(event=event, name="Team", normalized_name="team", leader=member)
        HackathonTeamMember.objects.create(event=event, team=team, member=member, application=application,
            creator=member, state="active")
    submission = HackathonSubmission.objects.create(event=event, team=team)
    snapshot = SubmissionSnapshot.objects.create(submission=submission, sequence=1, submitted_by=member,
        project={}, content_sha256="a"*64)
    role = EventRoleAssignment.objects.create(event=event, makerspace=tenant, member=judge, role="judge")
    round = JudgingRound.objects.create(event=event, key="final", mode="weighted_1_5",
        configuration={"criteria": [{"key": "quality"}]})
    assignment = JudgeAssignment.objects.create(event=event, round=round, judge_role_assignment=role,
        submission_snapshot=snapshot)
    row = JudgeScore.objects.create(event=event, makerspace=tenant, assignment=assignment,
        criterion_values={"quality": 4}, notes="Private notes", submitted_at=timezone.now())
    with enabled_encryption():
        operation = close_global("enable_transition", actor.pk, all_makerspaces=True)
        try:
            call_command("backfill_scoped_pii", makerspace=tenant.pk, model="events.JudgeScore",
                fence_operation=operation)
            assert is_envelope(raw(row, "notes"))
            assert raw(row, "criterion_values") == {"quality": 4}
            with pytest.raises(DatabaseError), transaction.atomic(), fence_operation(operation):
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE events_judgescore SET criterion_values=%s::jsonb WHERE id=%s",
                        [json.dumps({"quality": 5}),row.pk])
        finally:
            reopen(operation, actor.pk)
        operation = close_global("decrypt_rollback", actor.pk, all_makerspaces=True)
        try:
            call_command("decrypt_scoped_pii", makerspace=tenant.pk, model="events.JudgeScore",
                actor_id=actor.pk, confirm_makerspace=tenant.pk, fence_operation=str(operation))
            assert raw(row, "notes") == "Private notes"
            assert raw(row, "criterion_values") == {"quality": 4}
        finally:
            reopen(operation, actor.pk)


def test_rollback_refuses_mandatory_dob_before_any_other_model_is_mutated(age_world):
    parent, subject = create_subject(age_world, SubjectKind.APPLICATION)
    insert(age_world, subject, prepare(age_world, subject))
    actor, _, tenant, event = age_world
    operator = User.objects.create_superuser(username="dob-rollback-operator")
    reason = JudgingReason.objects.create(makerspace=tenant, event=event, actor=actor, body="Preserve")
    before = raw(reason, "body")
    operation = close_global("decrypt_rollback", operator.pk, all_makerspaces=True)
    try:
        # Mandatory finance envelopes now make every whole-tenant rollback refuse up front, so the
        # generic mandatory refusal fires before the birth-date one; either way nothing is mutated.
        with pytest.raises(CommandError, match="Mandatory encrypted fields cannot be rolled back"):
            call_command("decrypt_scoped_pii", makerspace=tenant.pk, actor_id=operator.pk,
                confirm_makerspace=tenant.pk, fence_operation=str(operation))
        assert raw(reason, "body") == before
        call_command("backfill_scoped_pii", makerspace=tenant.pk,
            model="events.EventAnswerDerivation", verify_only=True)
    finally:
        reopen(operation, operator.pk)
