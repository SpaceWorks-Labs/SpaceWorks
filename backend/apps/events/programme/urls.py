"""Exact frozen relative route lists; inert until G installs every policy registry."""

from django.urls import path

from .series_guests import SeriesGuestsView
from .views import EventDayView, EventFormValidateView, EventFormView, PublishingView, ReadinessView


# Relative to /api/v1/admin/ (like events.urls_admin).
admin_patterns = [
    path("events/<int:pk>/programme/readiness/", ReadinessView.as_view(), name="events-programme-admin-programme-readiness"),
    path("events/<int:pk>/programme/live/", EventDayView.as_view(), name="events-programme-admin-programme-live"),
    path("events/<int:pk>/programme/publishing/", PublishingView.as_view(), name="events-programme-admin-programme-publishing"),
    path("events/<int:pk>/forms/<slug:form_key>/", EventFormView.as_view(), name="events-programme-admin-form-detail"),
    path("events/<int:pk>/forms/<slug:form_key>/validate/", EventFormValidateView.as_view(), name="events-programme-admin-form-validate"),
]
series_patterns = [
    path("event-series/<int:pk>/guests/", SeriesGuestsView.as_view(), name="events-programme-series-guests"),
]


def account_patterns():
    """G may install these independently of Events tombstoning."""
    from apps.accounts.security_activity import MemberSecurityActivityView
    from apps.organizations.member_leave import MemberOrganizationLeaveView
    return [
        path("security-activity/", MemberSecurityActivityView.as_view(), name="member-security-activity"),
        path("organizations/<int:pk>/leave/", MemberOrganizationLeaveView.as_view(), name="member-organization-leave"),
    ]


def platform_patterns():
    from apps.operations.platform_insights import PlatformInsightsView
    return [path("platform/insights/", PlatformInsightsView.as_view(), name="admin-platform-insights")]
