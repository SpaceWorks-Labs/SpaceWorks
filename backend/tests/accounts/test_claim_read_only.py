import re
from datetime import date

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.claim_route_types import LocallyFiltered, ReadOnly
from apps.accounts.claim_routes import CLAIM_ROUTES
from apps.accounts.models import User
from apps.makerspaces import profile_services
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.models import AccountTimelineEntry as ProfileTimelineEntry

pytestmark = pytest.mark.django_db


READ_ONLY_CASES = (
    ("presence-projects", "GET", "presence-projects"),
    ("presence-projects", "HEAD", "presence-projects"),
    ("member-profile-timeline", "GET", "timeline"),
    ("member-profile-timeline", "HEAD", "timeline"),
    ("member-profile-timeline-detail", "GET", "timeline-detail"),
    ("member-profile-timeline-detail", "HEAD", "timeline-detail"),
    ("member-profile-achievements", "GET", "achievements"),
    ("member-profile-achievements", "HEAD", "achievements"),
    ("hardware_requests:equipment-kit-public-list", "GET", "kit-list"),
    ("hardware_requests:equipment-kit-public-list", "HEAD", "kit-list"),
    ("hardware_requests:equipment-kit-public-detail", "GET", "kit-detail"),
    ("hardware_requests:equipment-kit-public-detail", "HEAD", "kit-detail"),
    ("member-booking-list", "GET", "bookings"),
    ("member-booking-list", "HEAD", "bookings"),
    ("presence-current", "GET", "presence"),
    ("presence-current", "HEAD", "presence"),
    ("member-waiver", "GET", "waiver"),
    ("member-waiver", "HEAD", "waiver"),
    ("member-activity", "GET", "activity"),
    ("member-activity", "HEAD", "activity"),
    ("member-my-usage", "GET", "my-usage"),
    ("member-my-usage", "HEAD", "my-usage"),
    ("member-certifications", "GET", "certifications"),
    ("member-certifications", "HEAD", "certifications"),
    ("member-allowances", "GET", "allowances"),
    ("member-allowances", "HEAD", "allowances"),
    ("member-payment-history", "GET", "payments"),
    ("member-payment-history", "HEAD", "payments"),
    ("member-payment-documents", "GET", "payment-documents"),
    ("member-payment-documents", "HEAD", "payment-documents"),
    ("member-profile", "GET", "profile"),
    ("member-profile", "HEAD", "profile"),
    ("member-directory", "GET", "directory"),
    ("member-directory", "HEAD", "directory"),
    ("member-directory-detail", "GET", "directory-detail"),
    ("member-directory-detail", "HEAD", "directory-detail"),
)


def make_member():
    space = Makerspace.objects.create(name="Claim read space", slug="claim-read")
    user = User.objects.create_user(
        username="claim-read-member",
        email="claim-read@example.test",
        access_status=User.AccessStatus.ACTIVE,
    )
    membership = MakerspaceMembership.objects.create(
        user=user,
        makerspace=space,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=MakerspaceRole.objects.get(makerspace=space, slug="member"),
        status="active",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, space, membership


def case_url(case, space, membership, timeline_id=None):
    if case == "bookings":
        return f"/api/v1/public/{space.slug}/my-bookings/"
    if case in {"presence", "presence-projects"}:
        suffix = "current" if case == "presence" else "projects"
        return f"/api/v1/public/{space.slug}/presence-sessions/{suffix}"
    if case == "kit-list":
        return f"/api/v1/public/{space.slug}/equipment-kits/"
    if case == "kit-detail":
        return f"/api/v1/public/{space.slug}/equipment-kits/999999/"
    base = f"/api/v1/member/makerspaces/{space.pk}"
    return {
        "waiver": f"{base}/waiver",
        "activity": f"{base}/activity",
        "my-usage": f"{base}/my-usage",
        "certifications": f"{base}/certifications",
        "allowances": f"{base}/allowances",
        "payments": f"{base}/payments",
        "payment-documents": f"{base}/payment-documents",
        "profile": f"{base}/profile",
        "timeline": f"{base}/profile/timeline",
        "timeline-detail": f"{base}/profile/timeline/{timeline_id}",
        "achievements": f"{base}/profile/achievements",
        "achievement-detail": f"{base}/profile/achievements/{timeline_id}",
        "directory": f"{base}/directory",
        "directory-detail": f"{base}/directory/{membership.pk}",
    }[case]


@pytest.mark.parametrize("view_name,method,case", READ_ONLY_CASES)
def test_every_read_only_policy_executes_without_database_writes(
    view_name, method, case
):
    client, space, membership = make_member()
    if case == "directory-detail":
        profile_services.save_profile(membership, {"is_visible": True})
    timeline_id = None
    if case == "achievement-detail":
        from apps.makerspaces.models_account_profile import ProfileAchievement
        timeline_id = ProfileAchievement.objects.create(
            profile=profile_services.profile_for(membership), title="Existing self-reported entry").pk
    if case == "timeline-detail":
        profile = profile_services.profile_for(membership)
        entry = ProfileTimelineEntry.objects.create(
            profile=profile, kind="experience", title="Existing owned entry", start=date(2026, 1, 1),
        )
        timeline_id = entry.pk
    writes = []

    def capture(execute, sql, params, many, context):
        if re.match(r"^\s*(INSERT|UPDATE|DELETE)\b", sql, re.IGNORECASE):
            writes.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(capture):
        response = client.generic(method, case_url(case, space, membership, timeline_id))

    # Machine certifications were retired: the route answers a typed 410 and still writes nothing.
    # kit-detail has no published kit in this fixture: a typed 404, still without a write.
    expected = {"certifications": 410, "kit-detail": 404, "achievement-detail": 405}.get(case, 200)
    assert response.status_code == expected, getattr(response, "data", None)
    assert writes == []


def test_read_only_cases_cover_the_complete_matrix():
    expected = {
        key
        for key, policy in CLAIM_ROUTES.items()
        if isinstance(policy, (ReadOnly, LocallyFiltered))
    }
    assert {(name, method) for name, method, _case in READ_ONLY_CASES} == expected
