"""Decision 242 (role completeness): member 360, bulk decisions, search and the superadmin cross-space routes."""
from django.urls import path

from apps.admin_api.bulk_decisions import (
    BookingBulkDecideView, RefundCaseBulkDecideView, RegistrationBulkDecideView, RequestBulkDecideView,
)
from apps.admin_api.views_machine_bookings import MachineBookingListView
from apps.admin_api.views_member_activity import MemberActivityView
from apps.admin_api.views_platform_defaults import PlatformAdminListView, PlatformModuleDefaultsView
from apps.admin_api.views_platform_cross_space import (
    PlatformInboxView, PlatformQueuesView, PlatformSearchView, PlatformSnapshotView,
)

_SPACE = "makerspaces/<int:makerspace_id>"

urlpatterns = [
    path(f"{_SPACE}/members/<int:user_id>/activity", MemberActivityView.as_view(), name="admin-member-activity"),
    path(f"{_SPACE}/machine-bookings", MachineBookingListView.as_view(), name="admin-machine-bookings"),
    path("bulk/requests/<str:decision>", RequestBulkDecideView.as_view(), name="admin-bulk-requests"),
    path("bulk/bookings/<str:decision>", BookingBulkDecideView.as_view(), name="admin-bulk-bookings"),
    path("bulk/event-registrations/<str:decision>", RegistrationBulkDecideView.as_view(),
         name="admin-bulk-event-registrations"),
    path(f"{_SPACE}/refund-cases/bulk/<str:decision>", RefundCaseBulkDecideView.as_view(),
         name="admin-bulk-refund-cases"),
    path("platform/queues", PlatformQueuesView.as_view(), name="admin-platform-queues"),
    path("platform/spaces/<int:makerspace_id>/snapshot", PlatformSnapshotView.as_view(), name="admin-platform-space-snapshot"),
    path("platform/inbox", PlatformInboxView.as_view(), name="admin-platform-inbox"),
    path("platform/search", PlatformSearchView.as_view(), name="admin-platform-search"),
    # Open item C13: read-only module defaults and the platform admin list.
    path("platform/module-defaults", PlatformModuleDefaultsView.as_view(), name="admin-platform-module-defaults"),
    path("platform/admins", PlatformAdminListView.as_view(), name="admin-platform-admins"),
]
