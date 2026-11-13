"""Real ordinary/hackathon aggregates; infrastructure belongs to G's runner."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from apps.accounts.models import User
from apps.events.models import Event, EventRegistration
from apps.events.hackathons.admission_models import HackathonConfig, HackathonApplication
from apps.events.programme.form_models import EventFormRevision
from apps.events.staged_forms.definition_models import EventStageForm
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import grant_staff_role


@pytest.fixture(params=("ordinary", "hackathon"))
def stage_env(request, settings):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    now = timezone.now()
    space = Makerspace.objects.create(name="Stages", slug="stages-" + uuid4().hex[:10])
    space.enabled_modules = [key for key in space.enabled_modules if key not in ("notifications", "event_reimbursements")]
    space.save(update_fields=["enabled_modules"])
    space.enabled_features = list(set(space.enabled_features) | {"events.account_registration"})
    space.save(update_fields=["enabled_features"])
    owner = User.objects.create_user(username="owner-" + uuid4().hex[:10], account_kind="member")
    role = space.roles.get(slug="space_manager")
    # One account per person (decision 63): a plain person plus a staff-track row.
    manager = User.objects.create_user(username="staff-" + uuid4().hex[:10], account_kind="member")
    grant_staff_role(manager, space)
    event = Event.objects.create(makerspace=space, title=request.param, status="published", is_public=True,
        starts_at=now + timedelta(days=5), ends_at=now + timedelta(days=6), registration_audience="accounts")
    if request.param == "hackathon":
        HackathonConfig.objects.create(event=event, enabled=True)
    return SimpleNamespace(space=space, event=event, owner=owner, manager=manager, kind=request.param, now=now)


def definition(env, *, key="checklist", questions=None, **kwargs):
    values = dict(event=env.event, slug=key, title=key, state="published", stage="application",
        published_at=env.now - timedelta(hours=1), due_after_seconds=86400, lock_on_next_stage=False)
    values.update(kwargs)
    row = EventStageForm.objects.create(**values)
    revision = EventFormRevision.objects.create(event=env.event, form_key="stage", selector_kind="stage",
        selector_id=row.pk, revision=1, schema={"schema_version": 2, "form_id": str(row.form_id), "revision": 1,
            "questions": questions if questions is not None else [{"id": "answer", "type": "short_text", "label": "Answer", "required": True}]})
    row.current_revision = revision
    row.save(update_fields=["current_revision"])
    return row


def participant(env, *, status="registered"):
    row = EventRegistration.objects.create(event=env.event, member=env.owner, name="Maker", email="maker@example.test",
        phone="", registration_audience="accounts", status=status)
    application = None
    if env.kind == "hackathon":
        application = HackathonApplication.objects.create(event=env.event, member=env.owner, registration=row,
            state="submitted", submitted_at=timezone.now())
    return row, application


def payload(row, *, answers=None, **kwargs):
    return {"stage_form_id": row.pk, "form": {key: row.current_revision.schema[key] for key in
        ("schema_version", "form_id", "revision")}, "answers": answers if answers is not None else {"answer": "Ready"},
        "derivations": {}, "save_choices": {}, "saved_detail_versions": {}, "event_date_revision": row.event.event_date_revision, **kwargs}
