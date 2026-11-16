"""Decision 223 (i) walk-in registration and the scheduled guest-pass sweeps."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.makerspaces import guest_pass_issue, guest_pass_sweeps
from apps.makerspaces.models import GuestPass, GuestPassPolicy, MakerspaceMembership
from apps.makerspaces.walk_in_services import create_walk_in_member
from tests.makerspaces.test_guest_passes import _space, _sponsor
from tests.makerspaces.test_membership_j1 import manager, user

pytestmark = pytest.mark.django_db(transaction=True)


def test_walk_in_creates_a_guest_pass_not_a_membership_by_default_g1():
    makerspace = _space("wi-pass")
    result = create_walk_in_member(manager(makerspace), makerspace, display_name="Alex Walker", phone="123")
    assert isinstance(result, GuestPass) and result.kind == "day" and result.holder.is_walk_in
    assert not MakerspaceMembership.objects.filter(makerspace=makerspace, user=result.holder).exists()


def test_walk_in_setting_membership_keeps_todays_behaviour():
    makerspace = _space("wi-member")
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(walk_in_registration_creates="membership")
    result = create_walk_in_member(manager(makerspace), makerspace, display_name="Sam Walker")
    assert isinstance(result, MakerspaceMembership) and result.user.is_walk_in
    assert not GuestPass.objects.filter(makerspace=makerspace).exists()


def test_walk_in_with_guest_passes_off_keeps_todays_behaviour():
    from tests.makerspaces.test_membership_j1 import space
    makerspace = space("wi-off")
    result = create_walk_in_member(manager(makerspace), makerspace, display_name="Kit Walker")
    assert isinstance(result, MakerspaceMembership)


def test_walk_in_api_returns_the_guest_pass_outcome():
    from rest_framework.test import APIClient
    makerspace = _space("wi-api")
    client = APIClient()
    client.force_authenticate(manager(makerspace))
    response = client.post(f"/api/v1/admin/makerspaces/{makerspace.pk}/walk-in-members", {"display_name": "Rae Walker"},
                           format="json")
    assert response.status_code == 201, response.data
    assert response.data["guest_pass_id"] and response.data["is_walk_in"] is True
    assert response.data["waiver_accepted"] is False


def test_sweep_expires_ended_passes_and_notifies_holders_in_the_last_hour():
    makerspace = _space("sw-expire")
    ended, ending = user("sw-ended"), user("sw-ending")
    staff = manager(makerspace)
    old, _ = guest_pass_issue.issue_staff_pass(staff, makerspace, ended)
    soon, _ = guest_pass_issue.issue_staff_pass(staff, makerspace, ending)
    GuestPass.objects.filter(pk=old.pk).update(
        valid_from=timezone.now() - timedelta(hours=5), valid_until=timezone.now() - timedelta(minutes=1))
    GuestPass.objects.filter(pk=soon.pk).update(valid_until=timezone.now() + timedelta(minutes=30))
    counts = guest_pass_sweeps.run_guest_pass_sweeps()
    old.refresh_from_db()
    assert old.status == "expired" and counts["expired"] == 1 and counts["notified"] == 1
    again = guest_pass_sweeps.run_guest_pass_sweeps()
    assert again["expired"] == 0


def test_sweep_skips_spaces_with_the_capability_off():
    from tests.makerspaces.l4_helpers import features_off
    makerspace = _space("sw-off")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, user("sw-off-guest"))
    GuestPass.objects.filter(pk=row.pk).update(
        valid_from=timezone.now() - timedelta(hours=5), valid_until=timezone.now() - timedelta(minutes=1))
    features_off(makerspace, "guest_passes")
    assert guest_pass_sweeps.run_guest_pass_sweeps()["expired"] == 0
    row.refresh_from_db()
    assert row.status != "expired"


def test_membership_sweep_task_runs_the_guest_pass_sweep_without_a_new_beat_entry():
    from django.conf import settings
    from apps.makerspaces.tasks_membership import run_membership_renewals_task
    tasks = [entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()]
    assert tasks.count("apps.makerspaces.tasks_membership.run_membership_renewals_task") == 1
    assert not any("guest_pass" in task for task in tasks)
    makerspace = _space("sw-task")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, user("sw-task-guest"))
    GuestPass.objects.filter(pk=row.pk).update(
        valid_from=timezone.now() - timedelta(hours=5), valid_until=timezone.now() - timedelta(minutes=1))
    run_membership_renewals_task()
    row.refresh_from_db()
    assert row.status == "expired"
