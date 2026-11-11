"""Portable association admission protects tenant and borrower identity."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.data_export.loan_context_integrity import validate_loan_context_import
from apps.events.models import Event, EventRegistration
from apps.events.models_loan_context import EventLoanContext
from tests.test_request_workflow import make_space, make_product, make_hardware_request, make_user

pytestmark = pytest.mark.django_db


def test_cross_person_registration_cannot_pass_admission():
    space = make_space("context-import-subject")
    request = make_hardware_request(space, make_product(space))
    other = make_user("context-import-other")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=other, name="Other", email="other@example.test", phone="")
    EventLoanContext.objects.create(makerspace=space, request=request, event=event, participant_registration=registration, active=True)
    with pytest.raises(ValueError, match="borrower"):
        validate_loan_context_import(space.pk)
    registration.member = request.requester
    registration.save(update_fields=["member"])
    validate_loan_context_import(space.pk)


@pytest.mark.django_db(transaction=True)
def test_paired_activation_rotates_once_and_receipt_retry_preserves_generation(monkeypatch, settings):
    from cryptography.fernet import Fernet
    from apps.tenant_migration import cutover
    from apps.tenant_migration.models import MigrationReceipt
    from tests.tenant_migration.protocol_helpers import bind_job_state, import_job, signed_envelope, superadmin, target_pairing
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode("ascii")
    actor = superadmin("context-activate-root")
    pairing, source, private = target_pairing(actor)
    job = import_job(pairing)
    bind_job_state(monkeypatch, job)
    target = job.target_makerspace
    before = dict(target.loan_context_generations)
    envelope = signed_envelope(pairing, MigrationReceipt.Operation.SOURCE_CUTOVER, source, private)
    cutover.activate_target(pairing=pairing, import_job=job, receipt_envelope=envelope, actor=actor)
    target.refresh_from_db()
    first = dict(target.loan_context_generations)
    assert all(first[key] != before[key] for key in ("events", "bookings"))
    cutover.activate_target(pairing=pairing, import_job=job, receipt_envelope=envelope, actor=actor)
    target.refresh_from_db()
    assert target.loan_context_generations == first


def test_verified_transitive_merged_shell_is_same_borrower_not_unrelated():
    from tests.data_export.test_merged_fields import _merge
    space = make_space("context-alias-admission")
    survivor = make_user("context-alias-survivor")
    middle = make_user("context-alias-middle")
    shell = make_user("context-alias-shell")
    unrelated = make_user("context-alias-unrelated")
    request = make_hardware_request(space, make_product(space), requester=survivor)
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
    EventRegistration.objects.create(event=event, member=survivor, name="Survivor", email="survivor@example.test", phone="")
    registration = EventRegistration.objects.create(event=event, member=shell, name="Shell", email="shell@example.test", phone="")
    row = EventLoanContext.objects.create(makerspace=space, request=request, event=event, participant_registration=registration, active=True)
    _merge(shell, middle)
    _merge(middle, survivor)
    validate_loan_context_import(space.pk)
    registration.member = unrelated
    registration.save(update_fields=["member"])
    with pytest.raises(ValueError, match="borrower"):
        validate_loan_context_import(space.pk)
    row.refresh_from_db()
    assert row.request_id == request.pk


def test_historical_shell_request_matches_survivor_registration(monkeypatch):
    from tests.data_export.test_merged_fields import _merge
    space = make_space("context-shell-request")
    shell, survivor = make_user("context-shell-request-b"), make_user("context-shell-request-a")
    request = make_hardware_request(space, make_product(space), requester=shell)
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Event", starts_at=start, ends_at=start + timedelta(hours=1))
    registration = EventRegistration.objects.create(event=event, member=survivor, name="Member", email="a@example.test", phone="")
    row = EventLoanContext.objects.create(makerspace=space, request=request, event=event, participant_registration=registration, active=True)
    _merge(shell, survivor)
    # The existing _merge fixture preserves historical references on the shell.
    validate_loan_context_import(space.pk)
    registration.member = make_user("context-shell-unrelated")
    registration.save(update_fields=["member"])
    with pytest.raises(ValueError, match="borrower"):
        validate_loan_context_import(space.pk)
    assert row.request_id == request.pk
