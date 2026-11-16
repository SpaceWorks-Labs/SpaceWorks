"""X7: term kinds, the append-only standing history, rebuilding standing at a date, X17 extend."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.membership_plan_services import cancel_term, create_term
from apps.makerspaces.membership_renewals import _expire
from apps.makerspaces.membership_term_history import standing, standing_at
from apps.makerspaces.models import MembershipTermStatusEvent
from tests.makerspaces.l4_helpers import features_off, features_on, member, plan, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def test_opening_records_active_and_upcoming_rows():
    space, manager = space_with_manager("th-open")
    monthly = plan(space)
    membership = member("th-open", space)
    first = create_term(manager, membership, monthly)
    second = create_term(manager, membership, monthly)
    assert list(first.status_events.values_list("status", flat=True)) == ["active"]
    assert list(second.status_events.values_list("status", flat=True)) == ["upcoming", "active"]
    assert standing(second, timezone.now()) == "upcoming"
    assert AuditLog.objects.filter(action="membership.term_status_changed").count() == 3


def test_history_is_append_only():
    space, manager = space_with_manager("th-append")
    term = create_term(manager, member("th-append", space), plan(space))
    row = term.status_events.first()
    row.reason = "edited"
    with pytest.raises(RuntimeError):
        row.save()
    with pytest.raises(RuntimeError):
        row.delete()


def test_expiry_without_successor_is_lapsed_and_standing_rebuilds_from_history():
    space, manager = space_with_manager("th-lapse")
    membership = member("th-lapse", space)
    start = timezone.now() - timedelta(days=60)
    term = create_term(manager, membership, plan(space), starts_at=start)
    _expire(term)
    events = list(MembershipTermStatusEvent.objects.filter(term=term))
    assert events[-1].status == "lapsed"
    assert standing_at(events, start + timedelta(days=1)) == "active"
    assert standing_at(events, timezone.now()) == "lapsed"


def test_cancel_records_a_cancelled_row():
    space, manager = space_with_manager("th-cancel")
    term = create_term(manager, member("th-cancel", space), plan(space))
    cancel_term(manager, term, reason="Asked to stop")
    assert term.status_events.last().status == "cancelled"
    assert term.status_events.last().reason == "Asked to stop"


def test_reinstatement_after_a_gap():
    space, manager = space_with_manager("th-reinstate")
    membership = member("th-reinstate", space)
    monthly = plan(space)
    old = create_term(manager, membership, monthly, starts_at=timezone.now() - timedelta(days=200))
    _expire(old)
    again = create_term(manager, membership, monthly)
    assert again.kind == "reinstatement"


def test_extend_needs_a_reason_and_its_switch():
    space, manager = space_with_manager("th-extend")
    membership = member("th-extend", space)
    term = create_term(manager, membership, plan(space))
    client = authenticated_client(manager)
    url = reverse("admin-membership-extend", args=[membership.pk])
    assert client.post(url, {"reason": "Volunteer hours", "days": 30}, format="json").status_code == 404
    features_on(space, "renewal_desk")
    assert client.post(url, {"reason": "", "days": 30}, format="json").status_code == 400
    response = client.post(url, {"reason": "Volunteer hours", "days": 30}, format="json")
    assert response.status_code == 200, response.content
    term.refresh_from_db()
    assert term.status_events.last().status == "extended"
    assert term.status_events.last().reason == "Volunteer hours"
    assert AuditLog.objects.filter(action="membership.extended", target_id=str(term.pk)).exists()
    features_off(space, "renewal_desk")
    assert client.post(url, {"reason": "Again", "days": 5}, format="json").status_code == 404


def test_history_timeline_in_words_hides_staff_reasons_from_the_member():
    space, manager = space_with_manager("th-words")
    membership = member("th-words", space)
    term = create_term(manager, membership, plan(space, "Annual"))
    cancel_term(manager, term, reason="internal note")
    features_on(space, "history")
    staff = authenticated_client(manager).get(reverse("admin-membership-history", args=[membership.pk])).json()
    assert any(row["reason"] == "internal note" for row in staff)
    mine = authenticated_client(membership.user).get(
        reverse("member-membership-history", args=[space.pk])).json()
    assert {row["text"] for row in mine} >= {"Joined on the Annual plan", "The Annual term was cancelled"}
    assert all(row["reason"] == "" for row in mine)
    features_off(space, "history")
    assert authenticated_client(membership.user).get(
        reverse("member-membership-history", args=[space.pk])).status_code == 404
