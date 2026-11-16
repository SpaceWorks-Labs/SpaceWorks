import base64
from copy import copy
from uuid import uuid4

import pytest
from rest_framework.exceptions import NotFound

from apps.audit.models import AuditLog
from apps.events.credentials.boundary import event_command
from apps.events.credentials.crypto import prepare, token_digest, unwrap
from apps.events.credentials.errors import CredentialKeyUnavailable, ProgrammeConflict
from apps.events.credentials.models import EventRegistrationCredential
from apps.events.credentials.resolution import confirm, resolve
from apps.events.credentials.workflow import command, issue_locked, owner_payload, prepare_issue
from apps.events.models_attendance import EventCheckInEvent
from tests.events.checkin_helpers import make_event, make_member, make_space, make_staff, register

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def keys(settings):
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"e" * 32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"d" * 32).decode()


def prepared():
    space = make_space("programme-credential")
    event = make_event(space)
    operator = make_staff(space)
    member = make_member(space)
    registration = register(event, member)
    material = prepare_issue(event.pk, registration.pk)
    with event_command(event.pk, actor=operator, permission="check_in", account_ids=(member.pk,)) as (locked, actor):
        registration.event = locked
        credential = issue_locked(locked, registration, actor=actor, prepared=material)
    return event, operator, member, registration, credential


def test_opaque_ciphertext_binding_and_no_plaintext_in_model_or_audit():
    event, operator, member, registration, credential = prepared()
    payload = owner_payload(registration, actor=member)
    assert payload.startswith("SWEC2.") and len(payload) == 49
    assert payload.encode() not in bytes(credential.token_ciphertext)
    assert token_digest(event.pk + 1, payload) != credential.token_digest
    assert payload not in str(list(AuditLog.objects.values_list("meta", flat=True)))
    tampered = copy(credential)
    tampered.generation += 1
    with pytest.raises(CredentialKeyUnavailable):
        unwrap(tampered, event.pk)
    assert "SWEC2" not in repr(prepare(event.pk, registration.pk, 99))


def test_resolve_read_only_minimal_and_wrong_event_uniform():
    event, operator, member, registration, credential = prepared()
    payload = owner_payload(registration, actor=member)
    before = AuditLog.objects.count()
    result = resolve(event, payload, actor=operator)
    assert result["member_id"] == member.pk and result["confirmable"] is True
    assert set(result) == {"registration_id", "member_id", "name", "status", "attended_at",
                           "ticket_type_name", "host_waiver_state", "confirmable", "credential_generation"}
    assert not EventCheckInEvent.objects.exists() and AuditLog.objects.count() == before
    other = make_event(event.makerspace, "Other event")
    for token in (payload, "SWEC2.invalid", "junk"):
        with pytest.raises(NotFound):
            resolve(other, token, actor=operator)


def test_rotation_replay_and_cancel_never_resurrects_old_generation():
    event, operator, member, registration, old = prepared()
    payload = owner_payload(registration, actor=member)
    op = uuid4()
    result = command(event.pk, registration.pk, actor=operator, operation_id=op,
                     expected_version=event.version, action="rotate")
    assert command(event.pk, registration.pk, actor=operator, operation_id=op,
                   expected_version=event.version, action="rotate") == result
    assert EventRegistrationCredential.objects.filter(registration=registration).count() == 2
    with pytest.raises(NotFound):
        resolve(event, payload, actor=operator)
    with pytest.raises(ProgrammeConflict):
        command(event.pk, registration.pk, actor=operator, operation_id=op,
                expected_version=event.version, action="revoke")


def test_confirm_rechecks_generation_and_is_idempotent_but_resolve_after_attendance_still_identifies():
    event, operator, member, registration, credential = prepared()
    token = owner_payload(registration, actor=member)
    operation = uuid4()
    result = confirm(event.pk, token, actor=operator, operation_id=operation, credential_generation=1)
    assert result["status"] == "attended" and result["confirmable"] is False
    assert confirm(event.pk, token, actor=operator, operation_id=operation, credential_generation=1) == result
    assert EventCheckInEvent.objects.filter(registration=registration).count() == 1
    with pytest.raises(ProgrammeConflict):
        confirm(event.pk, token, actor=operator, operation_id=uuid4(), credential_generation=2)


def test_missing_keys_fail_closed_before_adoption_or_audit(settings):
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {}
    space = make_space("credential-no-key")
    event, member = make_event(space), make_member(space)
    registration = register(event, member)
    with pytest.raises(CredentialKeyUnavailable):
        prepare_issue(event.pk, registration.pk)
    registration.refresh_from_db()
    assert registration.credential_mode == "legacy"
    assert not EventRegistrationCredential.objects.filter(registration=registration).exists()
