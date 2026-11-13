"""Space-control routes (#185), mounted at api/v1/admin/ (superadmin) and api/v1/ (notices, public)."""

from django.urls import path

from .views_announcements import (
    AnnouncementCancelView, AnnouncementDetailView, AnnouncementListCreateView, PlatformNoticesView,
    PublicAvailabilityView,
)
from .views_controls import (
    ReadOnlyLiftView, ReadOnlyView, ScheduleCancelView, ScheduleView, SpaceHealthDetailView, SpaceHealthListView,
    SuspendView, TransferOwnershipView, UnsuspendView,
)
from .views_lifecycle import ArchiveNowView, PurgeView, UnarchiveView
from .views_onboarding import (
    HostingRequestApproveView, HostingRequestChangesView, HostingRequestDetailView, HostingRequestListView,
    HostingRequestRejectView,
)

SPACE = "platform/spaces/<int:makerspace_id>/"

admin_urlpatterns = [
    path("platform/space-health", SpaceHealthListView.as_view(), name="admin-platform-space-health"),
    path("platform/space-health/<int:makerspace_id>", SpaceHealthDetailView.as_view(),
         name="admin-platform-space-health-detail"),
    path(SPACE + "suspend", SuspendView.as_view(), name="admin-space-suspend"),
    path(SPACE + "unsuspend", UnsuspendView.as_view(), name="admin-space-unsuspend"),
    path(SPACE + "read-only", ReadOnlyView.as_view(), name="admin-space-read-only"),
    path(SPACE + "read-only/lift", ReadOnlyLiftView.as_view(), name="admin-space-read-only-lift"),
    path(SPACE + "schedule", ScheduleView.as_view(), name="admin-space-schedule"),
    path(SPACE + "schedule/cancel", ScheduleCancelView.as_view(), name="admin-space-schedule-cancel"),
    path(SPACE + "archive", ArchiveNowView.as_view(), name="admin-space-archive"),
    path(SPACE + "unarchive", UnarchiveView.as_view(), name="admin-space-unarchive"),
    path(SPACE + "purge", PurgeView.as_view(), name="admin-space-purge"),
    path(SPACE + "transfer-ownership", TransferOwnershipView.as_view(), name="admin-space-transfer-ownership"),
    path("platform/hosting-requests", HostingRequestListView.as_view(), name="admin-platform-hosting-requests"),
    path("platform/hosting-requests/<int:pk>", HostingRequestDetailView.as_view(),
         name="admin-platform-hosting-request"),
    path("platform/hosting-requests/<int:pk>/approve", HostingRequestApproveView.as_view(),
         name="admin-platform-hosting-request-approve"),
    path("platform/hosting-requests/<int:pk>/request-changes", HostingRequestChangesView.as_view(),
         name="admin-platform-hosting-request-changes"),
    path("platform/hosting-requests/<int:pk>/reject", HostingRequestRejectView.as_view(),
         name="admin-platform-hosting-request-reject"),
    path("platform/announcements", AnnouncementListCreateView.as_view(), name="admin-platform-announcements"),
    path("platform/announcements/<int:pk>", AnnouncementDetailView.as_view(), name="admin-platform-announcement"),
    path("platform/announcements/<int:pk>/cancel", AnnouncementCancelView.as_view(),
         name="admin-platform-announcement-cancel"),
]

urlpatterns = [
    path("platform-notices", PlatformNoticesView.as_view(), name="platform-notices"),
    path("public/makerspaces/<slug:makerspace_slug>/availability", PublicAvailabilityView.as_view(),
         name="public-makerspace-availability"),
]
