from django.urls import path

from .views_certificate_templates import (
    EventCertificateTemplateView, EventCertificatePreviewView,
    EventCertificateArtworkPresignView, EventCertificateArtworkFinalizeView, EventCertificateArtworkView,
)

urlpatterns = [
    path("events/<int:pk>/certificate-template/", EventCertificateTemplateView.as_view(), name="admin-event-certificate-template"),
    path("events/<int:pk>/certificate-template/preview.pdf", EventCertificatePreviewView.as_view(), name="admin-event-certificate-preview"),
    path("events/<int:pk>/certificate-artwork/", EventCertificateArtworkPresignView.as_view(), name="admin-event-certificate-artwork-presign"),
    path("events/<int:pk>/certificate-artwork/<int:artwork_id>/finalize/", EventCertificateArtworkFinalizeView.as_view(), name="admin-event-certificate-artwork-finalize"),
    path("events/<int:pk>/certificate-artwork/<int:artwork_id>/", EventCertificateArtworkView.as_view(), name="admin-event-certificate-artwork"),
]
