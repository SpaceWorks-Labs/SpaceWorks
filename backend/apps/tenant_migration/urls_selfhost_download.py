"""The one-use move-export download link (#190), beside the other one-use backup downloads."""

from django.urls import path

from .views_selfhost_moves_platform import SelfHostMoveDownloadView

urlpatterns = [
    path("api/v1/backups/selfhost-moves/<uuid:pk>/<str:token>", SelfHostMoveDownloadView.as_view(),
         name="selfhost-move-download"),
]
