"""Account utilities survive Events tombstoning and remain owner/session scoped."""
from django.urls import include, path

from .security_activity import MemberSecurityActivityView
from apps.organizations.member_leave import MemberOrganizationLeaveView
from apps.operations.platform_insights import PlatformInsightsView

urlpatterns = [
    path("member/saved-details/", include("apps.accounts.saved_details.urls")),
    path("member/security-activity/", MemberSecurityActivityView.as_view(), name="member-security-activity"),
    path("member/organizations/<int:pk>/leave/", MemberOrganizationLeaveView.as_view(), name="member-organization-leave"),
    path("admin/platform/insights/", PlatformInsightsView.as_view(), name="admin-platform-insights"),
]
