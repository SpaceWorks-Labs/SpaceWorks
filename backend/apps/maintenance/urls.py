"""Maintenance's staff API, relocated out of `admin_api` (plan B5/B6, phase 11).

Same contract as the warranty move in phase 10: mounted at `admin_api`'s own
`/api/v1/admin/` prefix with unchanged paths and unchanged route names, so the OpenAPI
snapshot, `makerspaces.origin_scope_routes` (keyed by bare `url_name`) and every
`reverse()` are unaffected. No `app_name`, for the same reason -- these names are
unnamespaced today and a namespace would break callers silently.
"""

from django.urls import path
from apps.maintenance.views_overdue import OverdueMaintenanceListView

from apps.maintenance.views import (
    MaintenanceLogDocumentDetailView,
    MaintenanceLogDocumentFinalizeView,
    MaintenanceLogDocumentPresignView,
    MaintenanceLogDocumentUrlView,
    MaintenanceLogListCreateView,
    MaintenanceScheduleDeactivateView,
    MaintenanceScheduleDetailView,
    MaintenanceScheduleListCreateView,
)

from .views_feed import MaintenanceFeedView, MaintenanceFeedCalendarView
from .views_work_orders import WorkOrderAssignView, WorkOrderListView, WorkOrderMoveView

urlpatterns = [
    # Lane L12: work orders, the one repair/maintenance job model (L16 builds on it).
    path("makerspaces/<int:makerspace_id>/work-orders", WorkOrderListView.as_view(), name="admin-work-orders"),
    path("work-orders/<int:pk>/status", WorkOrderMoveView.as_view(), name="admin-work-order-status"),
    path("work-orders/<int:pk>/assign", WorkOrderAssignView.as_view(), name="admin-work-order-assign"),
    path("makerspaces/<int:makerspace_id>/maintenance/feed", MaintenanceFeedView.as_view(), name="maintenance-feed"),
    path("makerspaces/<int:makerspace_id>/maintenance/feed/<str:raw_token>.ics", MaintenanceFeedCalendarView.as_view(), name="maintenance-feed-calendar"),
    path("makerspace/<int:makerspace_id>/maintenance-overdue", OverdueMaintenanceListView.as_view(), name="admin-maintenance-overdue"),
    # Schedules and logs hang off a machine; the per-row routes are flat because a
    # schedule or log id already identifies its machine.
    path(
        "makerspaces/<int:makerspace_id>/machines/<int:machine_id>/maintenance/schedules/",
        MaintenanceScheduleListCreateView.as_view(),
        name="admin-maintenance-schedule-list-create",
    ),
    path(
        "maintenance/schedules/<int:pk>/",
        MaintenanceScheduleDetailView.as_view(),
        name="admin-maintenance-schedule-detail",
    ),
    path(
        "maintenance/schedules/<int:pk>/deactivate/",
        MaintenanceScheduleDeactivateView.as_view(),
        name="admin-maintenance-schedule-deactivate",
    ),
    path(
        "makerspaces/<int:makerspace_id>/machines/<int:machine_id>/maintenance/logs/",
        MaintenanceLogListCreateView.as_view(),
        name="admin-maintenance-log-list-create",
    ),
    path(
        "maintenance/logs/<int:pk>/documents/presign/",
        MaintenanceLogDocumentPresignView.as_view(),
        name="admin-maintenance-log-document-presign",
    ),
    path(
        "maintenance/logs/<int:pk>/documents/",
        MaintenanceLogDocumentFinalizeView.as_view(),
        name="admin-maintenance-log-document-finalize",
    ),
    path(
        "maintenance/log-documents/<int:pk>/url/",
        MaintenanceLogDocumentUrlView.as_view(),
        name="admin-maintenance-log-document-url",
    ),
    path(
        "maintenance/log-documents/<int:pk>/",
        MaintenanceLogDocumentDetailView.as_view(),
        name="admin-maintenance-log-document-detail",
    ),
]

# Release 2 L16: issues, repairs, technicians and item/room maintenance (same admin prefix).
from .repairs.urls_staff import urlpatterns as _repairs_urlpatterns  # noqa: E402

urlpatterns += _repairs_urlpatterns

# Release 0.12.0 (decision 223): the incident register's staff routes.
from .incidents.urls import staff_urlpatterns as _incident_urlpatterns  # noqa: E402

urlpatterns += _incident_urlpatterns
