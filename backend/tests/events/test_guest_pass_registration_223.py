"""Decision 223 (a)(b): the event pass is issued when a registration becomes confirmed, and released on cancel."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import guest_pass_registration
from apps.events.models import EventRegistration
from apps.makerspaces.models import GuestPass
from tests.events.checkin_helpers import make_event, register
from tests.events.test_guest_pass_adapter_223 import _events_space
from tests.makerspaces.test_guest_passes import _sponsor
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)


def _passes(makerspace, holder=None):
    rows = GuestPass.objects.filter(makerspace=makerspace, kind="event")
    return rows.filter(holder=holder) if holder else rows


def test_a_non_member_gets_the_pass_the_moment_the_registration_is_confirmed():
    makerspace = _events_space("gr-issue")
    event = make_event(makerspace)
    guest = user("gr-guest")
    registration = register(event, guest)  # no check-in, no planning
    row = _passes(makerspace, guest).get()
    assert row.operation_id == f"event-{event.pk}-reg-{registration.pk}"


def test_pending_and_waitlisted_registrations_get_nothing_until_admitted():
    makerspace = _events_space("gr-wait")
    event = make_event(makerspace)
    guest = user("gr-wait-guest")
    registration = register(event, guest, status=EventRegistration.Status.WAITLISTED)
    assert not _passes(makerspace).exists()
    registration.status = EventRegistration.Status.REGISTERED
    registration.save(update_fields=["status"])
    assert _passes(makerspace, guest).count() == 1


def test_saving_again_or_checking_in_does_not_issue_a_second_pass():
    makerspace = _events_space("gr-idem")
    registration = register(make_event(makerspace), user("gr-idem-guest"))
    registration.save()
    registration.save(update_fields=["status"])
    guest_pass_registration.ensure_event_pass(registration.pk)
    assert _passes(makerspace).count() == 1


def test_members_and_account_less_registrants_get_no_pass():
    makerspace = _events_space("gr-skip")
    event = make_event(makerspace)
    register(event, _sponsor(makerspace, "gr-member"))
    register(event, None, email="walkin@example.test")
    assert not _passes(makerspace).exists()


def test_nothing_is_issued_while_the_events_capability_is_off():
    makerspace = _events_space("gr-off", adapter_on=False)
    register(make_event(makerspace), user("gr-off-guest"))
    assert not _passes(makerspace).exists()


def test_cancelling_the_registration_revokes_the_unused_pass():
    makerspace = _events_space("gr-cancel")
    guest = user("gr-cancel-guest")
    registration = register(make_event(makerspace), guest)
    registration.status = EventRegistration.Status.CANCELLED
    registration.save(update_fields=["status"])
    assert _passes(makerspace, guest).get().status == "revoked"


def test_a_pass_whose_holder_has_checked_in_survives_cancellation_and_is_audited():
    from apps.presence.models import PresenceSession
    makerspace = _events_space("gr-keep-presence")
    guest = user("gr-keep-guest")
    registration = register(make_event(makerspace), guest)
    row = _passes(makerspace, guest).get()
    now = timezone.now()
    PresenceSession.objects.create(member=guest, account=guest, makerspace=makerspace, status="guest",
                                   started_at=now, expires_at=now + timedelta(hours=2))
    registration.status = EventRegistration.Status.CANCELLED
    registration.save(update_fields=["status"])
    row.refresh_from_db()
    assert row.status != "revoked"
    assert AuditLog.objects.filter(action="membership.guest_pass_kept_on_cancel", makerspace=makerspace).exists()


def test_a_pass_whose_holder_has_items_out_survives_cancellation_and_is_audited():
    from apps.hardware_requests.models import HardwareRequest
    makerspace = _events_space("gr-keep-loan")
    guest = user("gr-loan-guest")
    registration = register(make_event(makerspace), guest)
    row = _passes(makerspace, guest).get()
    HardwareRequest.objects.create(makerspace=makerspace, requester=guest, status=HardwareRequest.Status.ISSUED,
                                   requested_for="Kit", issued_at=timezone.now())
    registration.status = EventRegistration.Status.CANCELLED
    registration.save(update_fields=["status"])
    row.refresh_from_db()
    assert row.status != "revoked"
    assert AuditLog.objects.filter(action="membership.guest_pass_kept_on_cancel", makerspace=makerspace).exists()


def test_cancel_then_register_again_issues_a_fresh_pass_and_cancel_revokes_that_one_too():
    makerspace = _events_space("gr-rereg")
    guest = user("gr-rereg-guest")
    registration = register(make_event(makerspace), guest)
    registration.status = EventRegistration.Status.CANCELLED
    registration.save(update_fields=["status"])
    assert _passes(makerspace, guest).get().status == "revoked"
    registration.status = EventRegistration.Status.REGISTERED
    registration.save(update_fields=["status"])
    rows = list(_passes(makerspace, guest).order_by("pk"))
    assert rows[0].status == "revoked" and rows[1].status in GuestPass.LIVE_STATUSES
    assert rows[1].operation_id == f"{rows[0].operation_id}-g2"
    registration.status = EventRegistration.Status.CANCELLED
    registration.save(update_fields=["status"])
    assert [row.status for row in _passes(makerspace, guest).order_by("pk")] == ["revoked", "revoked"]


def test_a_pass_staff_revoked_is_never_silently_reissued_on_re_registration():
    from apps.makerspaces.guest_pass_lifecycle import revoke_pass
    from apps.accounts.models import User
    makerspace = _events_space("gr-staffrev")
    guest = user("gr-staffrev-guest")
    registration = register(make_event(makerspace), guest)
    staff = User.objects.create_user(username="gr-staffrev-staff", email="gr-staffrev-staff@example.test", password="x")
    revoke_pass(staff, _passes(makerspace, guest).get(), reason="misuse")
    registration.save()
    guest_pass_registration.ensure_event_pass(registration.pk)
    assert _passes(makerspace, guest).count() == 1
