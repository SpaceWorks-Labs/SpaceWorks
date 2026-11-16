"""Real production F/P/A/C composition; PostgreSQL execution belongs to rerun."""
from dataclasses import replace
from uuid import uuid4
import pytest
from apps.forms_schema.submission import FormContextConflict
from apps.events import event_authority
from apps.events.capacity import spots_left, registration_spots_left
from apps.events.contracts.admission_registration import upload_policy_supported
from apps.events.hackathons import admission_ports
from apps.events.hackathons.admission_models import HackathonApplication
from apps.events.models import EventTicketType, EventRegistration, EventStaffGrant
from apps.events.contributions.models_roles import EventGrantEntitlement, EventRoleAssignment
from apps.events.programme.admission_forms import AdmissionForms
from apps.events.programme.prepared_forms import prepare, require_current
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.events.ticketing import available_ticket_types
from tests.events.programme.integration.g2a_support import canonical_world, apply, command

pytestmark = pytest.mark.django_db(transaction=True)


def production_forms(monkeypatch):
    monkeypatch.setattr(admission_ports, "_ports", replace(admission_ports.ports(), forms=AdmissionForms()))


def test_actual_form_port_creates_same_canonical_pending_registration(canonical_world, monkeypatch):
    production_forms(monkeypatch)
    row = apply(canonical_world)
    assert row.answers_snapshot == '{"version":2,"form_id":"application","form_revision":1,"answers":[]}'
    assert row.registration.custom_answers["answers"] == []
    assert row.registration.credential_mode == "inert"


def test_no_save_preparation_does_not_provision_account_key(canonical_world, monkeypatch):
    from apps.accounts.saved_details.models import SavedDetailUpdateIntent
    from apps.encryption.account_models import AccountPiiKey
    production_forms(monkeypatch)
    apply(canonical_world)
    assert not AccountPiiKey.objects.filter(user=canonical_world.owner).exists()
    assert not SavedDetailUpdateIntent.objects.filter(user=canonical_world.owner).exists()


def test_prepared_form_rejects_live_form_or_date_change(canonical_world):
    w = canonical_world
    subject = AnswerSubject(event_id=w.event.pk, owner_member_id=w.owner.pk,
        kind=SubjectKind.APPLICATION, creation_operation_id=uuid4())
    prepared = prepare(actor_id=w.owner.pk, subject=subject, schema=w.config.application_form,
        payload={"operation_id": subject.creation_operation_id, "form": {"schema_version": 2,
            "form_id": "application", "revision": 1}, "answers": {}})
    with pytest.raises(FormContextConflict) as caught:
        require_current(prepared, w.event, {**w.config.application_form, "revision": 2})
    assert caught.value.detail["code"] == "form_revision_changed"
    assert not HackathonApplication.objects.filter(event=w.event).exists()


@pytest.mark.parametrize("key", ["answers", "derivations", "save_choices", "coc"])
@pytest.mark.parametrize("invalid", [None, []])
def test_existing_form_edit_refuses_non_object_fields(canonical_world, key, invalid):
    from rest_framework.exceptions import ValidationError
    w = canonical_world
    row = apply(w)
    subject = AnswerSubject(event_id=w.event.pk, owner_member_id=w.owner.pk,
        kind=SubjectKind.APPLICATION, subject_id=row.pk)
    with pytest.raises(ValidationError) as caught:
        prepare(actor_id=w.owner.pk, subject=subject, schema=w.config.application_form,
            payload={key: invalid}, previous_answers=row.answers_snapshot)
    assert caught.value.detail["code"] == "invalid_form_payload"


@pytest.mark.parametrize("name,version,expected", [("hackathon-maker-v1", 1, True), ("unknown", 1, False),
    ("maker", 1, False), ("hackathon-maker-v1", 2, False), ("hackathon-maker-v1", True, False)])
def test_upload_policy_is_the_closed_registry_contract(name, version, expected):
    assert upload_policy_supported(name=name, version=version) is expected


def test_reserved_contributor_ticket_is_hidden_and_protects_its_seats(canonical_world):
    w = canonical_world
    w.event.capacity = 3
    w.event.save(update_fields=["capacity"])
    ticket = EventTicketType.objects.create(event=w.event, makerspace=w.space, name="Crew",
        purpose="contributor", contributor_capacity_policy="reserved_contributor_capacity", capacity=2)
    assert not available_ticket_types(w.event, w.owner).filter(pk=ticket.pk).exists()
    assert available_ticket_types(w.event, w.owner, contributor=True).filter(pk=ticket.pk).exists()
    assert spots_left(w.event) == 1
    assert registration_spots_left(w.event, ticket) == 2
    EventRegistration.objects.create(event=w.event, member=w.owner, name="Owner", email=w.owner.email,
        phone=w.owner.phone, status="registered")
    assert spots_left(w.event) == 0
    assert registration_spots_left(w.event, ticket) == 2


def test_cached_grant_union_alone_has_no_authority(canonical_world):
    w = canonical_world
    EventStaffGrant.objects.create(event=w.event, makerspace=w.space, user=w.owner,
        granted_by=w.manager, permissions=["check_in"])
    assert not event_authority.can(w.owner, w.event, "check_in")


def test_manual_source_loses_authority_when_issuer_becomes_inactive(canonical_world):
    w = canonical_world
    grant = EventStaffGrant.objects.create(event=w.event, makerspace=w.space, user=w.owner,
        granted_by=w.manager, permissions=["check_in"])
    EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="manual", permissions=["check_in"], created_by=w.manager)
    assert event_authority.can(w.owner, w.event, "check_in")
    w.manager.is_active = False
    w.manager.save(update_fields=["is_active"])
    assert not event_authority.can(w.owner, w.event, "check_in")


def test_revoking_manual_source_preserves_independent_role_source(canonical_world):
    from apps.events.services_staff_grants import revoke_grant
    w = canonical_world
    w.space.enabled_features += ["events.volunteering"]
    w.space.save(update_fields=["enabled_features"])
    grant = EventStaffGrant.objects.create(event=w.event, makerspace=w.space, user=w.owner,
        granted_by=w.manager, permissions=["check_in", "publish_schedule"])
    manual = EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="manual", permissions=["check_in"], created_by=w.manager)
    role = EventRoleAssignment.objects.create(event=w.event, makerspace=w.space, member=w.owner,
        role="volunteer", state="approved", approved_by=w.manager, delegated_permissions=["publish_schedule"])
    source = EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="role", role_assignment=role, permissions=["publish_schedule"], created_by=w.manager)
    revoke_grant(grant, actor=w.manager)
    manual.refresh_from_db()
    source.refresh_from_db()
    assert manual.revoked_at and source.revoked_at is None
    assert not event_authority.can(w.owner, w.event, "check_in")
    assert event_authority.can(w.owner, w.event, "publish_schedule")


def test_requirement_completion_is_bound_to_authored_posting_revision(canonical_world, monkeypatch):
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.contributions.models_roles import EventRolePosting
    from apps.events.contributions.runtime import ContributorPorts
    from apps.events.contributions import ports, requirements_workflow
    from apps.events.contributions.requirements_adapter import require_requirements
    from apps.events.contributions.errors import ProgrammeError
    w = canonical_world
    monkeypatch.setattr(ports, "_adapter", ContributorPorts())
    posting = EventRolePosting.objects.create(event=w.event, makerspace=w.space, role="volunteer",
        title="Setup", opens_at=timezone.now() - timedelta(days=1), closes_at=w.event.ends_at,
        requirements={"training_ids": [12]})
    role = EventRoleAssignment.objects.create(event=w.event, makerspace=w.space, member=w.owner,
        posting=posting, role="volunteer", state="applied", consent_revision=1)
    with pytest.raises(ProgrammeError) as caught:
        require_requirements(actor_id=w.owner.pk, assignment_id=role.pk, shift_id=None)
    assert caught.value.detail["code"] == "requirements_unmet"
    requirements_workflow.complete(actor=w.manager, event_id=w.event.pk, assignment_id=role.pk,
        payload=command(role.version, kind="training", reference_id=12))
    require_requirements(actor_id=w.owner.pk, assignment_id=role.pk, shift_id=None)
    posting.requirements = {"training_ids": [12], "briefing_ids": [13]}
    posting.save(update_fields=["requirements"])
    with pytest.raises(ProgrammeError):
        require_requirements(actor_id=w.owner.pk, assignment_id=role.pk, shift_id=None)


@pytest.mark.parametrize("disable", ["feature", "cancelled", "completed"])
def test_role_source_gate_never_revokes_independent_manual_permission(canonical_world, disable):
    w = canonical_world
    w.space.enabled_features += ["events.volunteering"]
    w.space.save(update_fields=["enabled_features"])
    grant = EventStaffGrant.objects.create(event=w.event, makerspace=w.space, user=w.owner,
        granted_by=w.manager, permissions=["check_in", "publish_schedule"])
    EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="manual", permissions=["check_in"], created_by=w.manager)
    role = EventRoleAssignment.objects.create(event=w.event, makerspace=w.space, member=w.owner,
        role="volunteer", state="approved", approved_by=w.manager, delegated_permissions=["publish_schedule"])
    EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="role", role_assignment=role, permissions=["publish_schedule"], created_by=w.manager)
    assert event_authority.can(w.owner, w.event, "publish_schedule")
    if disable == "feature":
        w.space.enabled_features.remove("events.volunteering")
        w.space.save(update_fields=["enabled_features"])
    else:
        w.event.status = disable
        w.event.save(update_fields=["status"])
    assert not event_authority.can(w.owner, w.event, "publish_schedule")
    assert event_authority.can(w.owner, w.event, "check_in")


def test_disabled_shift_source_cannot_check_in_but_manual_source_survives(canonical_world):
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.contributions.models_roles import EventRolePosting
    from apps.events.contributions.models_shifts import EventShift, EventShiftSignup, EventShiftAttendance
    w = canonical_world
    w.space.enabled_features += ["events.volunteering"]
    w.space.save(update_fields=["enabled_features"])
    now = timezone.now()
    w.event.starts_at, w.event.ends_at = now - timedelta(hours=1), now + timedelta(hours=2)
    w.event.save(update_fields=["starts_at", "ends_at"])
    posting = EventRolePosting.objects.create(event=w.event, makerspace=w.space, role="volunteer",
        title="Door", opens_at=w.event.starts_at, closes_at=w.event.ends_at, permission_preset=["check_in"])
    role = EventRoleAssignment.objects.create(event=w.event, makerspace=w.space, member=w.owner,
        posting=posting, role="volunteer", state="approved", approved_by=w.manager)
    shift = EventShift.objects.create(event=w.event, makerspace=w.space, posting=posting,
        starts_at=w.event.starts_at, ends_at=w.event.ends_at, signup_deadline=w.event.starts_at,
        task="Door", permission_preset=["check_in"])
    signup = EventShiftSignup.objects.create(event=w.event, makerspace=w.space, shift=shift,
        assignment=role, member=w.owner, state="approved", approved_by=w.manager)
    EventShiftAttendance.objects.create(event=w.event, makerspace=w.space, signup=signup)
    grant = EventStaffGrant.objects.create(event=w.event, makerspace=w.space, user=w.owner,
        granted_by=w.manager, permissions=["check_in", "publish_schedule"])
    EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="manual", permissions=["publish_schedule"], created_by=w.manager)
    EventGrantEntitlement.objects.create(event=w.event, makerspace=w.space, grant=grant,
        source_kind="shift", shift_signup=signup, permissions=["check_in"], created_by=w.manager)
    assert event_authority.can(w.owner, w.event, "check_in")
    w.space.enabled_features.remove("events.volunteering")
    w.space.save(update_fields=["enabled_features"])
    assert not event_authority.can(w.owner, w.event, "check_in")
    assert event_authority.can(w.owner, w.event, "publish_schedule")
