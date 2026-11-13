import base64
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.workflow import issue_locked, command
from apps.events.certificates.print_models import BadgePrintJob, BadgePrintResource, EventBadgeTemplateRevision
from apps.events.certificates.print_policy import require_job
from apps.events.certificates.print_workflow import create
from tests.events.checkin_helpers import make_space, make_event, make_member, make_staff, register
from tests.events.programme.certificates.test_layers import FIXTURES
import json

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def desk(settings):
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"e"*32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"d"*32).decode()
    space = make_space("programme-print")
    event, actor, member = make_event(space), make_staff(space), make_member(space)
    registration = register(event, member, status="attended")
    seed = json.loads((FIXTURES / "template-seed-v2.json").read_text())["badge_seed"]
    revision = EventBadgeTemplateRevision.objects.create(event=event, stock=seed["stock"], document=seed["document"])
    values = dict(operation_id=uuid4(), expected_version=event.version, registration_ids=[registration.pk],
                  template_revision=revision.pk, stock=revision.stock, include_photo=False)
    job = create(event.pk, actor=actor, **values)
    return event, actor, registration, job, values


def test_private_print_job_never_persists_raw_qr_and_same_command_replays(desk):
    event, actor, registration, job, values = desk
    require_job(job, actor)
    assert create(event.pk, actor=actor, **values).pk == job.pk
    assert job.resources.get(kind="qr").credential_generation == 1
    assert "SWEC2." not in json.dumps(job.template)
    with pytest.raises(ProgrammeConflict):
        create(event.pk, actor=actor, **{**values, "include_photo": True})


def test_preissued_job_url_denied_immediately_after_credential_rotation(desk):
    event, actor, registration, job, _values = desk
    command(event.pk, registration.pk, actor=actor, action="rotate", operation_id=uuid4(), expected_version=event.version)
    with pytest.raises(ProgrammeConflict):
        require_job(job, actor)


def test_expiry_denies_before_storage_and_cancellation_cannot_resurrect(desk):
    event, actor, registration, job, _values = desk
    job.expires_at = timezone.now()-timedelta(seconds=1)
    with pytest.raises(NotFound):
        require_job(job, actor)
    job.expires_at = timezone.now()+timedelta(hours=1)
    event.status = "cancelled"; event.save(update_fields=("status",))
    with pytest.raises(NotFound):
        require_job(job, actor)
