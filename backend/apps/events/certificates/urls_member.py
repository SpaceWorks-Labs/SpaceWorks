from django.urls import path

from .signatory_views import MemberApprovalListView, MemberApprovalPreviewView, MemberApproveView
from .output_views import (MyCertificateHolderNameView, MyCertificatePngView, MyCertificateShareImageView,
                           MyCertificatesView)

SPACE = "makerspaces/<int:makerspace_id>/"

urlpatterns = [
    # r2-idcards-best C4: a signatory reviews and approves designs that print their signature.
    path(SPACE + "certificate-approvals/", MemberApprovalListView.as_view(),
         name="events-programme-member-certificate-approvals"),
    path(SPACE + "certificate-approvals/<int:signatory_id>/designs/<int:revision_id>/preview.pdf",
         MemberApprovalPreviewView.as_view(), name="events-programme-member-certificate-approval-preview"),
    path(SPACE + "certificate-approvals/<int:signatory_id>/approve/", MemberApproveView.as_view(),
         name="events-programme-member-certificate-approve"),
    # r2-idcards-best C7-C9: your certificates, their PNG and share image, and whether your name is public.
    path(SPACE + "certificates/", MyCertificatesView.as_view(), name="events-programme-member-certificates"),
    path(SPACE + "certificates/<int:pk>/png/", MyCertificatePngView.as_view(), name="events-programme-member-certificate-png"),
    path(SPACE + "certificates/<int:pk>/share-image/", MyCertificateShareImageView.as_view(),
         name="events-programme-member-certificate-share-image"),
    path(SPACE + "certificates/<int:pk>/holder-name/", MyCertificateHolderNameView.as_view(),
         name="events-programme-member-certificate-holder-name"),
]
