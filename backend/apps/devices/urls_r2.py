"""Release-2 L10 machine-integration routes (foundation only; 404 while the capability is off)."""
from django.urls import path

from .views_integrations import (
    DeviceIntegrationJobReportView, DeviceIntegrationQueueView, TypeIntegrationDetailView,
    TypeIntegrationListView, TypeIntegrationStatusView,
)

integration_urlpatterns = [
    path("admin/makerspace/<int:makerspace_id>/machine-types/<int:type_id>/integrations",
         TypeIntegrationListView.as_view(), name="admin-machine-type-integration-list"),
    path("admin/makerspace/<int:makerspace_id>/machine-types/<int:type_id>/integration-status",
         TypeIntegrationStatusView.as_view(), name="admin-machine-type-integration-status"),
    path("admin/machine-type-integrations/<uuid:pk>", TypeIntegrationDetailView.as_view(),
         name="admin-machine-type-integration-detail"),
    path("device/integrations/queue", DeviceIntegrationQueueView.as_view(), name="device-integration-queue"),
    path("device/integrations/jobs/<int:pk>/report", DeviceIntegrationJobReportView.as_view(),
         name="device-integration-job-report"),
]
