from django.urls import path
from .library_views import (LibraryListView, LibraryDetailView, LibraryRevisionsView,
                            LibraryRevisionView, LibraryCopyView, LibraryCaptureView)
from .library_artwork_views import LibraryArtworkReserveView, LibraryArtworkFinalizeView

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/event-certificate-library/from-event/", LibraryCaptureView.as_view(), name="events-programme-tenant-admin-import-event"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/<int:template_id>/artwork/", LibraryArtworkReserveView.as_view(), name="events-programme-library-artwork-reserve"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/<int:template_id>/artwork/<int:artwork_id>/finalize/", LibraryArtworkFinalizeView.as_view(), name="events-programme-library-artwork-finalize"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/", LibraryListView.as_view(), name="events-programme-tenant-admin-list"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/<int:template_id>/", LibraryDetailView.as_view(), name="events-programme-tenant-admin-detail"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/<int:template_id>/revisions/", LibraryRevisionsView.as_view(), name="events-programme-tenant-admin-revisions-list"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/<int:template_id>/revisions/<int:revision_id>/", LibraryRevisionView.as_view(), name="events-programme-tenant-admin-revisions-detail"),
    path("makerspaces/<int:makerspace_id>/event-certificate-library/<int:template_id>/copy-to-event/", LibraryCopyView.as_view(), name="events-programme-tenant-admin-copy-to-event"),
]
