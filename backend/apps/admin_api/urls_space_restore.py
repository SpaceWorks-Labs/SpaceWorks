"""Per-space restore and the one backup schedule view (superadmin only)."""

from django.urls import path

from apps.backup.views_space_restore import (
    BackupScheduleView,
    SpaceRestoreAbortView,
    SpaceRestoreConfirmView,
    SpaceRestoreDetailView,
    SpaceRestoreListCreateView,
)

urlpatterns = [
    path("makerspace/<int:makerspace_id>/restores", SpaceRestoreListCreateView.as_view(),
         name="admin-makerspace-restores"),
    path("space-restores/<uuid:restore_id>", SpaceRestoreDetailView.as_view(), name="admin-space-restore"),
    path("space-restores/<uuid:restore_id>/confirm", SpaceRestoreConfirmView.as_view(),
         name="admin-space-restore-confirm"),
    path("space-restores/<uuid:restore_id>/abort", SpaceRestoreAbortView.as_view(),
         name="admin-space-restore-abort"),
    path("platform/backup-schedule", BackupScheduleView.as_view(), name="admin-backup-schedule"),
]
