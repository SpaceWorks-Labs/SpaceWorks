"""Device Adapter API v1 routes (device side signed; staff side under admin/)."""
from django.urls import path

from .views_adapter import (
    AdapterAccessAuthorizeView, AdapterBindingsView, AdapterCommandAckView, AdapterCommandLeaseView,
    AdapterEventsView, AdapterHelloView, AdapterSessionStartView, AdapterSessionStopView, AdapterStatusView,
    AdapterUsageLogView,
)

BASE = "device/adapter/v1/"
adapter_urlpatterns = [
    path(BASE + "hello", AdapterHelloView.as_view(), name="device-adapter-hello"),
    path(BASE + "bindings", AdapterBindingsView.as_view(), name="device-adapter-bindings"),
    path(BASE + "status", AdapterStatusView.as_view(), name="device-adapter-status"),
    path(BASE + "events", AdapterEventsView.as_view(), name="device-adapter-events"),
    path(BASE + "commands/lease", AdapterCommandLeaseView.as_view(), name="device-adapter-command-lease"),
    path(BASE + "commands/<uuid:pk>/ack", AdapterCommandAckView.as_view(), name="device-adapter-command-ack"),
    path(BASE + "access/authorize", AdapterAccessAuthorizeView.as_view(), name="device-adapter-access"),
    path(BASE + "sessions/start", AdapterSessionStartView.as_view(), name="device-adapter-session-start"),
    path(BASE + "sessions/<int:pk>/stop", AdapterSessionStopView.as_view(), name="device-adapter-session-stop"),
    path(BASE + "usage", AdapterUsageLogView.as_view(), name="device-adapter-usage"),
]

from .views_adapter_member import JobOwnerWatchView, ViewerEndView, ViewerFrameView, ViewerSignalView  # noqa: E402
from .views_adapter_more import (  # noqa: E402
    AdapterJobAckView, AdapterJobFileView, AdapterJobLeaseView, AdapterJobProgressView, AdapterJobReportView,
    AdapterKioskEvidenceView, AdapterKioskIssueView, AdapterKioskReturnView, AdapterKioskScanView,
    AdapterKioskSessionView, AdapterKioskStartView, AdapterMediaRecordingView, AdapterMediaSignalView,
    AdapterMediaSnapshotView,
)

adapter_urlpatterns += [
    path(BASE + "jobs/lease", AdapterJobLeaseView.as_view(), name="device-adapter-job-lease"),
    path(BASE + "jobs/<uuid:pk>/ack", AdapterJobAckView.as_view(), name="device-adapter-job-ack"),
    path(BASE + "jobs/<uuid:pk>/progress", AdapterJobProgressView.as_view(), name="device-adapter-job-progress"),
    path(BASE + "jobs/<uuid:pk>/report", AdapterJobReportView.as_view(), name="device-adapter-job-report"),
    path(BASE + "jobs/<uuid:pk>/file", AdapterJobFileView.as_view(), name="device-adapter-job-file"),
    path(BASE + "kiosk/sessions", AdapterKioskStartView.as_view(), name="device-adapter-kiosk-start"),
    path(BASE + "kiosk/sessions/<str:sid>", AdapterKioskSessionView.as_view(), name="device-adapter-kiosk-end"),
    path(BASE + "kiosk/sessions/<str:sid>/scan", AdapterKioskScanView.as_view(), name="device-adapter-kiosk-scan"),
    path(BASE + "kiosk/sessions/<str:sid>/evidence", AdapterKioskEvidenceView.as_view(),
         name="device-adapter-kiosk-evidence"),
    path(BASE + "kiosk/sessions/<str:sid>/issue", AdapterKioskIssueView.as_view(), name="device-adapter-kiosk-issue"),
    path(BASE + "kiosk/sessions/<str:sid>/return", AdapterKioskReturnView.as_view(),
         name="device-adapter-kiosk-return"),
    path(BASE + "media/<uuid:watch_id>/signal", AdapterMediaSignalView.as_view(), name="device-adapter-media-signal"),
    path(BASE + "media/<uuid:watch_id>/snapshot", AdapterMediaSnapshotView.as_view(),
         name="device-adapter-media-snapshot"),
    path(BASE + "media/<uuid:watch_id>/recording", AdapterMediaRecordingView.as_view(),
         name="device-adapter-media-recording"),
    path("member/adapter-watch/requests/<int:request_id>", JobOwnerWatchView.as_view(),
         name="member-adapter-watch-start"),
    path("member/adapter-watch/<uuid:pk>", ViewerEndView.as_view(), name="member-adapter-watch-end"),
    path("member/adapter-watch/<uuid:pk>/signal", ViewerSignalView.as_view(), name="member-adapter-watch-signal"),
    path("member/adapter-watch/<uuid:pk>/frame", ViewerFrameView.as_view(), name="member-adapter-watch-frame"),
]

from .views_adapter_media import (  # noqa: E402
    AdapterAccessCacheView, AdapterArtifactCompleteView, AdapterArtifactRequestView, AdapterConfigAckView,
    AdapterConfigView, AdapterOfflineDecisionsView, AdapterTimeView,
)
from .views_adapter_media_staff import (  # noqa: E402
    AdapterConfigVersionsView, ArtifactUrlView, BindingArtifactListView, BindingDetectionListView,
    BindingLogBundleView, BindingTelemetryView, MemberArtifactListView, MemberArtifactUrlView,
    MemberDetectionListView, ViewerTalkView,
)

adapter_urlpatterns += [
    path(BASE + "artifacts", AdapterArtifactRequestView.as_view(), name="device-adapter-artifact-request"),
    path(BASE + "artifacts/<uuid:pk>/complete", AdapterArtifactCompleteView.as_view(),
         name="device-adapter-artifact-complete"),
    path(BASE + "access/cache", AdapterAccessCacheView.as_view(), name="device-adapter-access-cache"),
    path(BASE + "access/offline-decisions", AdapterOfflineDecisionsView.as_view(),
         name="device-adapter-offline-decisions"),
    path(BASE + "config", AdapterConfigView.as_view(), name="device-adapter-config"),
    path(BASE + "config/ack", AdapterConfigAckView.as_view(), name="device-adapter-config-ack"),
    path(BASE + "time", AdapterTimeView.as_view(), name="device-adapter-time"),
    path("admin/adapter-bindings/<uuid:pk>/artifacts", BindingArtifactListView.as_view(),
         name="admin-adapter-artifacts"),
    path("admin/adapter-artifacts/<uuid:pk>/url", ArtifactUrlView.as_view(), name="admin-adapter-artifact-url"),
    path("admin/adapter-bindings/<uuid:pk>/detections", BindingDetectionListView.as_view(),
         name="admin-adapter-detections"),
    path("admin/adapter-bindings/<uuid:pk>/telemetry", BindingTelemetryView.as_view(), name="admin-adapter-telemetry"),
    path("admin/adapter-bindings/<uuid:pk>/log-bundle", BindingLogBundleView.as_view(),
         name="admin-adapter-log-bundle"),
    path("admin/adapters/<uuid:pk>/config-versions", AdapterConfigVersionsView.as_view(),
         name="admin-adapter-config-versions"),
    path("member/adapter-artifacts/requests/<int:request_id>", MemberArtifactListView.as_view(),
         name="member-adapter-artifacts"),
    path("member/adapter-artifacts/<uuid:pk>/url", MemberArtifactUrlView.as_view(), name="member-adapter-artifact-url"),
    path("member/adapter-detections/requests/<int:request_id>", MemberDetectionListView.as_view(),
         name="member-adapter-detections"),
    path("member/adapter-watch/<uuid:pk>/talk", ViewerTalkView.as_view(), name="member-adapter-watch-talk"),
]

from .urls_adapter_admin import admin_urlpatterns  # noqa: E402

adapter_urlpatterns += admin_urlpatterns
