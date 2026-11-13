"""Public programme routes under /api/v1/public/ (mounted only while the app ships)."""
from django.urls import path

from .views_public import (PublicProgrammeDetailView, PublicProgrammeJoinPhotoView,
                           PublicProgrammeJoinView, PublicProgrammeListView, PublicProgrammePrefillView)

_PROGRAMME = "organizations/<slug:slug>/id-programmes/<slug:programme_slug>"

urlpatterns = [
    path("organizations/<slug:slug>/id-programmes", PublicProgrammeListView.as_view(),
         name="public-organization-id-programmes"),
    path(_PROGRAMME, PublicProgrammeDetailView.as_view(), name="public-id-programme"),
    path(f"{_PROGRAMME}/join", PublicProgrammeJoinView.as_view(), name="public-id-programme-join"),
    path(f"{_PROGRAMME}/prefill", PublicProgrammePrefillView.as_view(), name="public-id-programme-prefill"),
    path(f"{_PROGRAMME}/join/photo", PublicProgrammeJoinPhotoView.as_view(), name="public-id-programme-join-photo"),
]
