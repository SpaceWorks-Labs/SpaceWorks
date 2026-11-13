"""Integration fixtures run after G imports models and authors shared migrations."""

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from django.db import transaction

from apps.accounts.models import User
from apps.encryption.services import get_or_create_active_dek
from apps.events.answer_derivations.preparation import prepare_derivations
from apps.events.answer_derivations.subjects import binding_for, subject_model
from apps.events.answer_derivations.workflow import insert_prepared_locked
from apps.events.contracts.providers import LockedContext
from apps.events.contracts.subjects import SubjectKind
from apps.events.models_event import Event
from apps.makerspaces.models import Makerspace
from tests.encryption.conftest import enabled_encryption


@pytest.fixture
def age_world():
    owner = User.objects.create_user(username=f"dob-owner-{uuid4().hex[:8]}")
    foreign = User.objects.create_user(username=f"dob-foreign-{uuid4().hex[:8]}")
    space = Makerspace.objects.create(name="Source DOB Space", slug=f"source-dob-{uuid4().hex[:8]}")
    event = Event.objects.create(
        makerspace=space, title="Derived ages", starts_at=datetime(2026, 12, 1, tzinfo=UTC),
        ends_at=datetime(2026, 12, 2, tzinfo=UTC), timezone_name="UTC", event_date_revision=7,
    )
    with enabled_encryption():
        get_or_create_active_dek(space.pk)
        yield owner, foreign, space, event


def create_subject(world, kind, *, role="mentor", member=None):
    owner, _, _, event = world
    values = {"event": event, "member": member or owner}
    if kind == SubjectKind.REGISTRATION:
        values.update(name="Owner", email=f"{owner.pk}@example.test", phone="+15555555555")
    elif kind == SubjectKind.ROLE_ASSIGNMENT:
        values.update(makerspace_id=event.makerspace_id, role=role, origin="self", state="draft")
    else:
        values["state"] = "draft"
    row = subject_model(kind).objects.create(**values)
    return row, binding_for(row, kind)


@contextmanager
def locked(world, subject):
    _, _, space, event = world
    from apps.events.programme_locks import fences
    with transaction.atomic(), fences(account_ids=[subject.owner_member_id], tenant_ids=[space.pk]):
        Event.objects.select_for_update().get(pk=event.pk)
        yield LockedContext(event_id=event.pk, tenant_ids=(space.pk,), account_ids=(subject.owner_member_id,))


def prepare(world, subject, *, dob="2004-05-12", revision=7, as_of="2026-12-01"):
    owner, _, _, _ = world
    return prepare_derivations(
        actor_id=owner.pk, subject=subject, derivations={"age": {
            "source": {"kind": "inline_dob", "date_of_birth": dob},
            "reviewed_event_date_revision": revision, "reviewed_as_of_date": as_of,
        }}, visible_question_ids=("age",), form_sha256="a" * 64, canonical_answer_sha256="b" * 64,
    )


def insert(world, subject, prepared):
    with locked(world, subject) as locks:
        return insert_prepared_locked(
            prepared, actor_id=world[0].pk, subject=subject, locks=locks,
            form_sha256="a" * 64, canonical_answer_sha256="b" * 64,
        )
