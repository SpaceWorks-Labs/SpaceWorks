"""Real A/G/F/ledger/credential boundary; unused external providers fail loudly."""
import base64
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection

from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.events.hackathons import admission_ports
from apps.events.hackathons.admission_models import HackathonConfig, HackathonCocRevision
from apps.events.hackathons.admission_ports import PreparedAnswers
from apps.events.hackathons.admission_workflow import save_application
from apps.events.registration_form_adapter import validate_registration_form
from apps.forms_schema.submission import validate_submission
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event


def command(version, **values):
    return {"operation_id": uuid4(), "expected_version": version, **values}


def unused(**kwargs):
    raise AssertionError("This scenario must not call an unrelated provider")


class BasicForms:
    """Use real F validation and P lifecycle, with no vault choices or DOB input."""
    def prepare(self, *, event, config, actor, subject, payload, draft):
        assert not connection.in_atomic_block, "Form preparation ran under domain locks"
        trusted = validate_registration_form(payload, schema=config.application_form, subject=subject,
                                             validator=validate_submission, application=True)
        validated = trusted.require_subject(subject)
        assert not validated.derivations and not any(validated.save_choices.values())
        return PreparedAnswers(snapshot=validated.snapshot, form_sha256=self.digest(config), subject=subject,
            normalized_input=payload, trusted_registration_form=trusted)

    def digest(self, config):
        return hashlib.sha256(json.dumps(config.application_form, sort_keys=True).encode()).hexdigest()

    def require_current_locked(self, *, config, prepared, **kwargs):
        assert self.digest(config) == prepared.form_sha256

    def attach_locked(self, **kwargs):
        return None

    def lock_answers_locked(self, *, application, locks, closing=False, **kwargs):
        from apps.events.answer_derivations.lifecycle import lock_subject_locked
        return lock_subject_locked(actor_id=application.member_id, subject=AnswerSubject(
            event_id=application.event_id, owner_member_id=application.member_id,
            kind=SubjectKind.APPLICATION, subject_id=application.pk), locks=locks, closing=closing)

    def archive_answers_locked(self, *, application, **kwargs):
        from apps.events.answer_derivations.models import EventAnswerDerivation
        assert not EventAnswerDerivation.objects.filter(application=application).exists()


@pytest.fixture
def canonical_world(monkeypatch, settings):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"q" * 32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"h" * 32).decode()
    suffix = uuid4().hex[:8]
    space = event_space(f"g2a-{suffix}")
    space.enabled_features += ["events.hackathons"]
    space.save(update_fields=["enabled_features"])
    event = open_event(space, capacity=1, payment_amount=12)
    owner, other = account(f"g2a-owner-{suffix}"), account(f"g2a-other-{suffix}")
    manager = make_staff(space)
    config = HackathonConfig.objects.create(event=event, enabled=True, review_mode="auto", offer_capacity=2,
        application_form={"schema_version": 2, "form_id": "application", "revision": 1, "questions": []})
    HackathonCocRevision.objects.create(event=event, revision=1, body="Be considerate.")
    monkeypatch.setattr(admission_ports, "_ports", None)
    notices = []
    admission_ports.install_production(forms=BasicForms(), context_gate=lambda **kwargs: None,
        readiness=unused, public_profile=unused, reviewer_candidates=unused, subject_conflict=unused,
        has_submission=unused, reopen_submission_locked=unused,
        enqueue_notice=lambda **kwargs: notices.append(kwargs), assert_encryption_ready=lambda **kwargs: None,
        storage_budget_used=unused, storage_budget_limit=unused, upload_policy_supported=unused,
        default_attendance_required=lambda **kwargs: True)
    return SimpleNamespace(space=space, event=event, owner=owner, other=other, manager=manager,
                           config=config, notices=notices)


def apply(world, member=None, **admission):
    member = member or world.owner
    payload = command(0, form={"schema_version": 2, "form_id": "application", "revision": 1}, answers={},
        event_date_revision=world.event.event_date_revision, coc={"revision": 1, "accepted": True}, **admission)
    return save_application(event=world.event, actor=member, payload=payload, submit=True)[0]
