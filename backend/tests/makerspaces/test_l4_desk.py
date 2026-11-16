"""Renewal desk, invite links, bulk decisions, public plans, register and the monthly summary."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.membership_admission_settings import update_settings
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.models import MembershipInviteLink, MembershipRequest, MembershipSummaryOptOut
from apps.operations.models_report_schedules import ReportSchedule
from tests.makerspaces.l4_helpers import features_off, features_on, member, plan, space_with_manager
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db


def _verified(username):
    return make_user(username, access_status="active", email_verified_at=timezone.now())


def test_worklist_and_one_reminder_per_member_per_day():
    space, manager = space_with_manager("desk-remind")
    membership = member("desk-remind", space)
    create_term(manager, membership, plan(space), starts_at=timezone.now() - timedelta(days=25))
    client = authenticated_client(manager)
    worklist = reverse("admin-membership-renewal-worklist", args=[space.pk])
    assert client.get(worklist).status_code == 404
    features_on(space, "renewal_desk")
    rows = client.get(worklist).json()
    assert [row["id"] for row in rows] == [membership.pk] and rows[0]["desk"]["standing"] == "active"
    remind = reverse("admin-membership-renewal-reminders", args=[space.pk])
    assert client.post(remind, {"membership_ids": [membership.pk]}, format="json").json()["sent"] == [membership.pk]
    assert client.post(remind, {"membership_ids": [membership.pk]}, format="json").json()["skipped"] == [membership.pk]
    assert AuditLog.objects.filter(action="membership.renewal_reminder_sent").count() == 1
    assert client.get(worklist).json()[0]["desk"]["reminded_today"] is True


def test_invite_link_admits_to_an_invite_only_space_until_used_up():
    space, manager = space_with_manager("desk-invite")
    update_settings(manager, space, {"join_mode": "invite_only"})
    client = authenticated_client(manager)
    links = reverse("admin-membership-invite-links", args=[space.pk])
    assert client.post(links, {"max_uses": 1}, format="json").status_code == 404
    features_on(space, "admission_tools")
    created = client.post(links, {"label": "Open day", "max_uses": 1}, format="json").json()
    code = created["code"]
    assert len(MembershipInviteLink.objects.get().code_digest) == 64 and code not in str(MembershipInviteLink.objects.values())
    public = reverse("public-membership-invite", args=[space.slug, code])
    assert client.get(public).json()["valid"] is True
    join = reverse("public-membership-request", args=[space.slug])
    first = authenticated_client(_verified("desk-invite-a")).post(join, {"invite_code": code}, format="json")
    assert first.status_code == 201, first.content
    second = authenticated_client(_verified("desk-invite-b")).post(join, {"invite_code": code}, format="json")
    assert second.status_code == 404
    refused = authenticated_client(_verified("desk-invite-c")).post(join, {}, format="json")
    assert refused.status_code == 400 and refused.json()["code"] == "membership_invite_required"


def test_bulk_decide_handles_each_request_on_its_own():
    space, manager = space_with_manager("desk-bulk")
    update_settings(manager, space, {"join_mode": "approval"})
    join = reverse("public-membership-request", args=[space.slug])
    for name in ("desk-bulk-a", "desk-bulk-b"):
        authenticated_client(_verified(name)).post(join, {}, format="json")
    ids = list(MembershipRequest.objects.filter(makerspace=space).values_list("pk", flat=True))
    features_on(space, "admission_tools")
    from tests.accounts.reauth_helpers import force_recent_authenticate
    client = authenticated_client(manager)
    force_recent_authenticate(client, manager)
    response = client.post(reverse("admin-membership-join-requests-bulk-decide", args=[space.pk]),
                           {"request_ids": [*ids, 999999], "decision": "approve"}, format="json")
    assert response.status_code == 200, response.content
    results = {row["id"]: row for row in response.json()}
    assert all(results[pk]["ok"] for pk in ids) and results[999999]["code"] == "not_found"
    assert AuditLog.objects.filter(action="membership.bulk_decided").exists()


def test_public_plans_and_the_plan_choice_on_join():
    space, manager = space_with_manager("desk-public")
    update_settings(manager, space, {"join_mode": "approval"})
    listed = plan(space, "Student", amount="5.00", is_public=True, slug="student", description="For students")
    plan(space, "Hidden")
    url = reverse("public-membership-plans", args=[space.slug])
    assert authenticated_client(manager).get(url).status_code == 404
    features_on(space, "public_plans")
    rows = authenticated_client(manager).get(url).json()
    assert [row["slug"] for row in rows] == ["student"]
    detail = reverse("public-membership-plan-detail", args=[space.slug, "student"])
    assert authenticated_client(manager).get(detail).json()["name"] == "Student"
    join = reverse("public-membership-request", args=[space.slug])
    authenticated_client(_verified("desk-public-a")).post(join, {"plan_id": listed.pk}, format="json")
    assert MembershipRequest.objects.get(makerspace=space).selected_plan_id == listed.pk
    features_off(space, "public_plans")
    refused = authenticated_client(_verified("desk-public-b")).post(join, {"plan_id": listed.pk}, format="json")
    assert refused.status_code == 400


def test_register_filters_by_standing():
    space, manager = space_with_manager("desk-register")
    ending = member("desk-reg-a", space)
    create_term(manager, ending, plan(space), starts_at=timezone.now() - timedelta(days=25))
    member("desk-reg-b", space)
    features_on(space, "register_tools")
    url = reverse("admin-member-register", args=[space.pk])
    client = authenticated_client(manager)
    assert {row["standing"] for row in client.get(url).json()} >= {"ending_soon", "no_term"}
    assert len(client.get(url, {"standing": "ending_soon"}).json()) == 1
    assert client.get(url, {"standing": "bogus"}).status_code == 400


def test_monthly_summary_preset_and_personal_opt_out():
    space, manager = space_with_manager("desk-summary")
    url = reverse("admin-membership-summary", args=[space.pk])
    client = authenticated_client(manager)
    assert client.get(url).status_code == 404
    features_on(space, "monthly_summary")
    assert client.put(url, {"enabled": True}, format="json").json()["enabled"] is True
    schedule = ReportSchedule.objects.get(makerspace=space, report_key="membership-monthly-summary")
    assert schedule.cadence == "monthly" and schedule.recipient_actions == ["manage_members"]
    assert client.put(url, {"opted_out": True}, format="json").json()["opted_out"] is True
    from apps.makerspaces.membership_summary import opted_out_user_ids
    assert manager.pk in opted_out_user_ids(schedule)
    features_off(space, "monthly_summary")
    from apps.operations.report_registry import REPORT_REGISTRY
    from apps.operations.report_schedule_services import _skip_reason
    assert _skip_reason(schedule, REPORT_REGISTRY[schedule.report_key]) == "feature_disabled:membership.monthly_summary"
    assert MembershipSummaryOptOut.objects.filter(makerspace=space).count() == 1
