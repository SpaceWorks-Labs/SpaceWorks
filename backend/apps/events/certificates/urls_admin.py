from django.urls import path
from .views import (BulkIssueView, BatchView, PrintCreateView, PrintDetailView, PrintDownloadView,
                    BadgeDesignView, DeskDesignView, CertificateRevokeView, CertificateReissueView, CertificateEligibilityView)
from .publication_views import CertificatePublicationView
from .print_preview import BadgePreviewView

from .seed_views import SeedCatalogueView, SeedInstallView, SeedPreviewView

urlpatterns = [
    path("events/<int:pk>/design-seeds/", SeedCatalogueView.as_view(), name="events-programme-admin-design-seeds"),
    path("events/<int:pk>/design-seeds/install/", SeedInstallView.as_view(), name="events-programme-admin-design-seed-install"),
    path("events/<int:pk>/design-seeds/preview.pdf", SeedPreviewView.as_view(), name="events-programme-admin-design-seed-preview"),
    path("events/<int:pk>/badges/design-preview.pdf", BadgePreviewView.as_view(), name="events-programme-admin-badge-design-preview"),
    path("events/<int:pk>/certificates/verification-policy/", CertificatePublicationView.as_view(), name="events-programme-admin-certificate-publication-policy"),
    path("events/<int:pk>/certificates/eligibility/", CertificateEligibilityView.as_view(), name="events-programme-admin-certificate-eligibility"),
    path("events/<int:pk>/certificates/bulk/", BulkIssueView.as_view(), name="events-programme-admin-certificates-bulk"),
    path("events/<int:pk>/certificates/batches/<int:batch_id>/", BatchView.as_view(), name="events-programme-admin-certificates-batches"),
    path("events/<int:pk>/certificates/<int:certificate_id>/revoke/", CertificateRevokeView.as_view(), name="events-programme-admin-certificates-revoke"),
    path("events/<int:pk>/certificates/<int:certificate_id>/reissue/", CertificateReissueView.as_view(), name="events-programme-admin-certificates-reissue"),
    path("events/<int:pk>/badges/designs/", BadgeDesignView.as_view(), name="events-programme-admin-badge-design"),
    path("events/<int:pk>/badges/desk-design/", DeskDesignView.as_view(), name="events-programme-admin-badge-desk-design"),
    path("events/<int:pk>/badges/print-jobs/", PrintCreateView.as_view(), name="events-programme-admin-badge-print-create"),
    path("events/<int:pk>/badges/print-jobs/<int:job_id>/", PrintDetailView.as_view(), name="events-programme-admin-badge-print-detail"),
    path("events/<int:pk>/badges/print-jobs/<int:job_id>/download/", PrintDownloadView.as_view(), name="events-programme-admin-badge-print-download"),
]
