from django.urls import path
from .output_views import PublicShareCardView, PublicShareImageView
from .verification import CertificateVerificationView

urlpatterns = [path("event-certificates/<uuid:verification_id>/verify/", CertificateVerificationView.as_view(),
                    name="events-programme-public-certificate-verify"),
               # r2-idcards-best C8: link-preview image for a publicly verifiable certificate.
               path("event-certificates/<uuid:verification_id>/share.png", PublicShareImageView.as_view(),
                    name="events-programme-public-certificate-share-image"),
               path("event-certificates/<uuid:verification_id>/share/", PublicShareCardView.as_view(),
                    name="events-programme-public-certificate-share-card")]
