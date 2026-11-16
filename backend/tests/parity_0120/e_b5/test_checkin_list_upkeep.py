"""D22: list order, restore, a 60-second scan undo, waitlist override, counts and the guardian re-check."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events import checkin_lists
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.models import EventCheckInListScan, EventRegistration
from apps.managed_hosting.extra_quotas import ExtraQuotaReached
from tests.events.collab_helpers import client_for, make_member
from tests.events.test_registration_cancel_api import register
from tests.parity_0120.e_b5.helpers import world

pytestmark = pytest.mark.django_db


def lists_world(slug, capacity=0):
    space, event, staff = world(slug, "events.checkin_lists", capacity=capacity)
    member = make_member(space, f"{slug}-m")
    return space, event, staff, member, register(event, member)


def test_reorder_restore_and_the_per_event_limit():
    space, event, staff, _member, _reg = lists_world("cl-a")
    one = checkin_lists.create(event, actor=staff, data={"name": "One"})
    two = checkin_lists.create(event, actor=staff, data={"name": "Two"})
    assert (one.position, two.position) == (1, 2)
    checkin_lists.reorder(event, actor=staff, ordered_ids=[two.pk, one.pk])
    one.refresh_from_db()
    two.refresh_from_db()
    assert (two.position, one.position) == (1, 2)
    with pytest.raises(ProgrammeError):
        checkin_lists.reorder(event, actor=staff, ordered_ids=[two.pk])  # must name every open list
    checkin_lists.update(event, actor=staff, list_id=one.pk, data={"archive": True})
    restored = checkin_lists.update(event, actor=staff, list_id=one.pk, data={"restore": True})
    assert restored.archived_at is None
    space.resource_limit_overrides = {"checkin_lists": 2}
    space.save(update_fields=["resource_limit_overrides"])
    with pytest.raises(ExtraQuotaReached):
        checkin_lists.create(event, actor=staff, data={"name": "Three"})


def test_undo_works_inside_a_minute_keeps_the_row_and_frees_the_collection():
    _space, event, staff, _member, registration = lists_world("cl-b")
    swag = checkin_lists.create(event, actor=staff, data={"name": "Swag"})
    scan, _ = checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk,
                                 operation_id=uuid4())
    checkin_lists.undo(event, actor=staff, list_id=swag.pk, scan_id=scan.pk)
    assert EventCheckInListScan.objects.filter(pk=scan.pk, undone_at__isnull=False).exists()
    assert checkin_lists.used(swag, registration) == 0
    again, _ = checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk,
                                  operation_id=uuid4())
    EventCheckInListScan.objects.filter(pk=again.pk).update(scanned_at=timezone.now() - timedelta(minutes=2))
    with pytest.raises(ProgrammeError) as late:
        checkin_lists.undo(event, actor=staff, list_id=swag.pk, scan_id=again.pk)
    assert late.value.detail["code"] == "undo_window_closed"
    with pytest.raises(ProgrammeError) as twice:
        checkin_lists.undo(event, actor=staff, list_id=swag.pk, scan_id=scan.pk)
    assert twice.value.detail["code"] == "already_undone"


def test_waitlisted_guest_needs_the_override_and_pending_never_passes():
    _space, event, staff, _member, registration = lists_world("cl-c")
    swag = checkin_lists.create(event, actor=staff, data={"name": "Swag"})
    EventRegistration.objects.filter(pk=registration.pk).update(status="waitlisted")
    with pytest.raises(ProgrammeError) as refused:
        checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk,
                           operation_id=uuid4())
    assert refused.value.detail["code"] == "waitlisted"
    _scan, (_allowed, used, reason) = checkin_lists.scan(
        event, actor=staff, list_id=swag.pk, registration_id=registration.pk, operation_id=uuid4(), override=True)
    assert (used, reason) == (1, None)
    EventRegistration.objects.filter(pk=registration.pk).update(status="pending_approval")
    with pytest.raises(ProgrammeError) as pending:
        checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk,
                           operation_id=uuid4(), override=True)
    assert pending.value.detail["code"] == "not_confirmed"


def test_counts_and_routes():
    _space, event, staff, _member, registration = lists_world("cl-d")
    swag = checkin_lists.create(event, actor=staff, data={"name": "Swag"})
    checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=registration.pk, operation_id=uuid4())
    shown = checkin_lists.project(swag)
    assert (shown["eligible"], shown["collected"], shown["collected_people"]) == (1, 1, 1)
    url = reverse("events-programme-admin-checkin-list-scan", kwargs={"pk": event.pk, "list_id": swag.pk})
    second = register(event, make_member(event.makerspace, "cl-d2"))
    posted = client_for(staff).post(url, {"operation_id": str(uuid4()), "registration_id": second.pk}, format="json")
    assert posted.status_code == 201 and posted.data["scan_id"]
    undo = reverse("events-programme-admin-checkin-list-scan-undo",
                   kwargs={"pk": event.pk, "list_id": swag.pk, "scan_id": posted.data["scan_id"]})
    assert client_for(staff).post(undo).status_code == 200
