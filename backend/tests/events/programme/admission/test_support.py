"""Contract doubles for A-only PostgreSQL tests, not the G2 integration proof."""
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.events.models import Event, EventRegistration
from apps.events.contracts.subjects import AnswerSubject
from apps.events.hackathons import admission_ports, admission_transactions
from apps.events.hackathons.admission_models import HackathonApplication, HackathonConfig, HackathonCocRevision
from apps.events.hackathons.admission_ports import AdmissionIntegrations, PreparedAnswers, OwnerAnswers
from tests.events.ticketing_helpers import account, event_space, open_event


def cmd(version=1, **kwargs):
    return {"operation_id": uuid4(), "expected_version": version, **kwargs}


class Forms:
    def prepare(self, *, event, config, actor, subject, payload, draft):
        return PreparedAnswers(snapshot={"version": 2, "form_id": "application", "form_revision": 1,
            "answers": [{"id": key, "label": key, "type": "short_text", "value": value}
                        for key, value in payload.get("answers", {}).items()]}, form_sha256="f" * 64,
            subject=subject, normalized_input=payload, trusted_registration_form=object())

    def require_current_locked(self, **kwargs):
        pass

    def attach_locked(self, **kwargs):
        return None

    def project_owner(self, *, application, snapshot):
        from zoneinfo import ZoneInfo
        return OwnerAnswers(answers=snapshot.get("answers", []), answer_review={
            "event_date_revision": application.event.event_date_revision,
            "as_of_date": application.event.starts_at.astimezone(ZoneInfo(application.event.timezone_name)).date().isoformat(),
            "locked": bool(application.answer_locked_at), "date_review_required": application.date_review_required})

    def project_intent(self, **kwargs):
        return None

    def lock_answers_locked(self, **kwargs):
        return None

    def archive_answers_locked(self, **kwargs):
        return None

    def validate_schema(self, schema):
        return schema


class Bridge:
    def __init__(self):
        self.calls = []

    def create_pending_locked(self, *, event, member, contacts, prepared, **kwargs):
        row = EventRegistration.objects.create(event=event, member=member, name=member.username,
            email=contacts["email"], phone=contacts["phone"], status="pending_approval",
            custom_answers=prepared.snapshot, quoted_amount=0)
        self.calls.append((row.pk, "pending"))
        return row.pk

    def transition_locked(self, *, registration_id, transition, **kwargs):
        # Test double for the sole G-owned status writer. These tests certify A's
        # calls/atomicity only; real ledger/waiver/QR bridging remains a G2 gate.
        row = EventRegistration.objects.get(pk=registration_id)
        row.status = {"offer": "pending_approval", "confirm": "registered", "cancel": "cancelled",
                      "waitlist": "waitlisted", "reject": "rejected", "reopen": "pending_approval", "event_cancel": "cancelled"}[transition]
        row.save(update_fields=["status"])
        self.calls.append((row.pk, transition))
        return row.pk

    def mirror_answers_locked(self, **kwargs):
        pass


@pytest.fixture
def world(monkeypatch, settings):
    settings.PII_ENCRYPTION_ENABLED = False
    space = event_space("programme-a")
    event = open_event(space, capacity=1)
    owner, other = account("a-owner"), account("a-other")
    config = HackathonConfig.objects.create(event=event, enabled=True, review_mode="auto", offer_capacity=2,
        application_form={"schema_version": 2, "form_id": "application", "revision": 1, "questions": []})
    HackathonCocRevision.objects.create(event=event, revision=1, body="Be considerate.")
    bridge, forms, notices, order = Bridge(), Forms(), [], []
    def lock_event(*, event_id, **kwargs):
        order.append("event")
        return Event.objects.select_for_update().get(pk=event_id)
    @contextmanager
    def fences(**kwargs):
        order.append("fences")
        yield
    def scopes(*, event_id, account_ids):
        return ((space.pk,), tuple(sorted(set(account_ids) | set(
            HackathonApplication.objects.filter(event_id=event_id).values_list("member_id", flat=True)))))
    integrations = AdmissionIntegrations(registration=bridge, forms=forms, fences=fences, lock_event=lock_event,
        context_gate=lambda **kwargs: None, readiness=lambda **kwargs: "ready", public_profile=lambda **kwargs: None,
        reviewer_candidates=lambda **kwargs: (), subject_conflict=lambda **kwargs: False, has_submission=lambda **kwargs: False, reopen_submission_locked=lambda **kwargs: None,
        enqueue_notice=lambda **kwargs: notices.append(kwargs), assert_encryption_ready=lambda **kwargs: None,
        event_scopes=scopes, default_attendance_required=lambda **kwargs: True, upload_policy_supported=lambda **kwargs: True, storage_budget_used=lambda **kwargs: 0, storage_budget_limit=lambda **kwargs: None)
    monkeypatch.setattr(admission_ports, "_ports", integrations)
    monkeypatch.setattr(admission_transactions, "feature_enabled", lambda *args: True)
    monkeypatch.setattr(admission_transactions, "boundary_tenant_write", lambda *args: nullcontext())
    # Authority itself is tested by G's policy suite; this double isolates A state.
    monkeypatch.setattr("apps.events.event_authority.require", lambda *args: None)
    monkeypatch.setattr("apps.events.event_authority.get_event", lambda actor, pk, permission: Event.objects.get(pk=pk))
    return SimpleNamespace(space=space, event=event, owner=owner, other=other, config=config,
                           bridge=bridge, forms=forms, notices=notices, order=order)


def submitted(world, member=None, state="offered"):
    member = member or world.owner
    registration = EventRegistration.objects.create(event=world.event, member=member, name=member.username,
        email=member.email, phone=member.phone, status="pending_approval", quoted_amount=0)
    from datetime import timedelta
    return HackathonApplication.objects.create(event=world.event, member=member, registration=registration,
        state=state, submitted_at=timezone.now(), coc_revision=1, coc_accepted_at=timezone.now(),
        offered_at=timezone.now(), rsvp_due_at=timezone.now() + timedelta(days=4))
