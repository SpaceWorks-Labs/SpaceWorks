from django.urls import path
from .verification import CertificateVerificationView

urlpatterns = [path("event-certificates/<uuid:verification_id>/verify/", CertificateVerificationView.as_view(),
                    name="events-programme-public-certificate-verify")]
