"""Owner-specific page editors, classified/attached by the integration lane."""

from django.urls import path
from .public_page_editor_views import (
    PageEditorView, PagePublishView, PageUnpublishView, PageHandleView,
    PageHandleAvailabilityView, PagePreviewView, PageRevisionsView,
)
from .public_page_asset_views import PageAssetsView, PageAssetDetailView


def patterns(prefix, kind):
    base = f"{prefix}/<int:pk>/public-page/"
    return [path(base + suffix, view.as_view(), {"kind": kind}, name=f"{kind}-public-page-{name}")
            for suffix, view, name in (
                ("", PageEditorView, "editor"), ("publish/", PagePublishView, "publish"),
                ("unpublish/", PageUnpublishView, "unpublish"), ("handle/", PageHandleView, "handle"),
                ("handle-availability/", PageHandleAvailabilityView, "handle-availability"),
                ("assets/", PageAssetsView, "assets"), ("assets/<int:asset_id>/", PageAssetDetailView, "asset"),
                ("preview/", PagePreviewView, "preview"), ("revisions/", PageRevisionsView, "revisions"))]


urlpatterns = patterns("makerspaces", "makerspace") + patterns("organizations", "organization")
