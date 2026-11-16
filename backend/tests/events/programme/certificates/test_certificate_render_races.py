from datetime import timedelta
import pytest
from django.utils import timezone

from apps.events.certificates.issuance import create_for_subject_locked
from apps.events.certificates.preparation import prepare_issuance
from apps.events.certificates.lifecycle import _claim_render, _activate, _fail_render
from apps.events.credentials.boundary import event_command
from apps.events.exceptions import EventInvalidTransition
from apps.events.models_certificates import EventAttendanceCertificate
from tests.events.checkin_helpers import make_event, make_member, make_space, register

pytestmark = pytest.mark.django_db(transaction=True)


def test_expired_render_claim_can_be_recovered_without_old_worker_activating_or_failing_new_claim():
    space = make_space("certificate-claim-recovery")
    event, member = make_event(space), make_member(space)
    registration = register(event, member, status="attended")
    prepared = prepare_issuance(event.pk, [{"subject_kind": "registration", "subject_id": registration.pk}])
    with event_command(event.pk, account_ids=prepared.account_ids, revalidate=prepared.revalidate) as (locked, _):
        row = create_for_subject_locked(locked, subject_kind="registration", subject_id=registration.pk, prepared=prepared)
    first = _claim_render(row.pk)
    with pytest.raises(EventInvalidTransition):
        _claim_render(row.pk)
    EventAttendanceCertificate.objects.filter(pk=row.pk).update(render_started_at=timezone.now()-timedelta(minutes=6))
    second = _claim_render(row.pk)
    assert second.render_token != first.render_token and second.render_attempts == 2
    with pytest.raises(EventInvalidTransition):
        _activate(row.pk, 100, "a"*64, render_token=first.render_token)
    _fail_render(row.pk, render_token=first.render_token)
    row.refresh_from_db()
    assert row.status == "rendering" and row.render_token == second.render_token
