"""Staff card-engine routes under /api/v1/admin/ (release 2 L3).

Design routes are id-only and reachable by every editor kind (member-card staff,
programme managers, event organisers), so they are classified DELEGABLE; member-card
routes keep the space prefix.
"""
from django.urls import path

from apps.makerspaces.member_card_admin_views_l3 import (
    MemberCardDownloadView, MemberCardEmailView, MemberCardPhotoRequestView, MemberCardPresenceView,
    MemberCardSettingsView,
)

from .views_approval import CardApprovalLevelsView
from .views_archive import CardDesignArchiveView, CardDesignUnarchiveView
from .views_assets import (CardAssetContentView, CardAssetFinalizeView, CardAssetUploadView, CardFontFileView,
                           CardFontListView, CardFontPrepareView)
from .views_design_actions import (CardDesignApproveView, CardDesignExportView, CardDesignImportView,
                                   CardDesignPreviewView, CardDesignPublishView, CardDesignRejectView,
                                   CardDesignResetView, CardDesignSubmitView)
from .views_designs import CardDesignDetailView, CardTemplateListView, SpaceCardDesignListView
from .views_history import (CardDesignCalibrationView, CardDesignHolderListView, CardDesignRestoreView,
                            CardDesignRevisionDetailView, CardDesignRevisionListView)
from .views_sheet_preview import MemberCardSheetPreviewView
from .views_staff_photo import MemberCardStaffPhotoView
from .views_org_default import OrganizationMemberCardDesignView
from .views_badges import (CardDesignBadgeConvertView, CardDesignBadgeExportView, CardDesignBadgeImportView,
                           EventBadgeDesignRoleView, EventBadgeDesignsView)
from .views_print_face import MemberCardPrintFaceView
from .views_title_cards import CardNumberSchemeListView, CardNumberSchemeTitleView, TitleCardListView
from .views_verify_staff import CardVerificationStaffView
from .views_staff_card_output import (StaffCardDesignView, StaffCardDownloadView, StaffCardJobListView,
                                      StaffCardPrintFaceView, StaffCardSettingsView)
from .views_staff_cards import (StaffCardBulkIssueView, StaffCardDetailView, StaffCardListView,
                                StaffCardReissueView, StaffCardRevokeView)
from .views_jobs import CardJobCancelView, CardJobDetailView, CardJobResultView, MemberCardJobListView
from .wallet.views_credentials import PlatformWalletCredentialsView, SpaceWalletCredentialsView
from .wallet.views_guest import GuestPassScanView

_SPACE = "makerspaces/<int:makerspace_id>"
_ORG = "organizations/<int:organization_id>"
_DESIGN = "card-designs/<int:pk>"

urlpatterns = [
    path(f"{_SPACE}/member-card-settings", MemberCardSettingsView.as_view(), name="admin-member-card-settings"),
    path(f"{_SPACE}/card-designs", SpaceCardDesignListView.as_view(), name="admin-card-designs"),
    path(f"{_ORG}/card-designs/member-cards", OrganizationMemberCardDesignView.as_view(),
         name="admin-organization-member-card-design"),
    path(f"{_SPACE}/card-designs/titles", TitleCardListView.as_view(), name="admin-card-design-titles"),
    path(f"{_SPACE}/card-number-schemes", CardNumberSchemeListView.as_view(), name="admin-card-number-schemes"),
    path(f"{_SPACE}/card-number-schemes/titles/<int:title_id>", CardNumberSchemeTitleView.as_view(),
         name="admin-card-number-scheme-title"),
    path("card-verifications/<str:token>/staff", CardVerificationStaffView.as_view(),
         name="admin-card-verification-staff"),
    path("member-cards/<int:pk>/print-face", MemberCardPrintFaceView.as_view(), name="admin-member-card-print-face"),
    path(f"{_SPACE}/card-approval-levels", CardApprovalLevelsView.as_view(), name="admin-card-approval-levels"),
    # Decision 223(k)/(l): wallet-pass credentials (space, platform) and the guest-pass desk scan.
    path(f"{_SPACE}/wallet-credentials", SpaceWalletCredentialsView.as_view(), name="admin-wallet-credentials"),
    path("platform/wallet-credentials", PlatformWalletCredentialsView.as_view(),
         name="admin-platform-wallet-credentials"),
    path(f"{_SPACE}/guest-passes/scan", GuestPassScanView.as_view(), name="admin-guest-pass-scan"),
    path(f"{_SPACE}/member-card-jobs", MemberCardJobListView.as_view(), name="admin-member-card-jobs"),
    path(f"{_SPACE}/member-card-jobs/preview", MemberCardSheetPreviewView.as_view(),
         name="admin-member-card-job-preview"),
    path(f"{_SPACE}/member-cards/presence-check-in", MemberCardPresenceView.as_view(),
         name="admin-member-card-presence"),
    path("member-cards/<int:pk>/download", MemberCardDownloadView.as_view(), name="admin-member-card-download"),
    path("member-cards/<int:pk>/email", MemberCardEmailView.as_view(), name="admin-member-card-email"),
    path("member-cards/<int:pk>/photo", MemberCardStaffPhotoView.as_view(), name="admin-member-card-photo"),
    path("member-cards/<int:pk>/photo-request", MemberCardPhotoRequestView.as_view(),
         name="admin-member-card-photo-request"),
    # O-B4 part 2: staff ID cards (module `membership` + capability `membership.staff_cards`).
    path(f"{_SPACE}/staff-cards", StaffCardListView.as_view(), name="admin-staff-cards"),
    path(f"{_SPACE}/staff-cards/bulk-issue", StaffCardBulkIssueView.as_view(), name="admin-staff-cards-bulk-issue"),
    path(f"{_SPACE}/staff-cards/settings", StaffCardSettingsView.as_view(), name="admin-staff-card-settings"),
    path(f"{_SPACE}/staff-card-design", StaffCardDesignView.as_view(), name="admin-staff-card-design"),
    path(f"{_SPACE}/staff-card-jobs", StaffCardJobListView.as_view(), name="admin-staff-card-jobs"),
    path("staff-cards/<int:pk>", StaffCardDetailView.as_view(), name="admin-staff-card"),
    path("staff-cards/<int:pk>/reissue", StaffCardReissueView.as_view(), name="admin-staff-card-reissue"),
    path("staff-cards/<int:pk>/revoke", StaffCardRevokeView.as_view(), name="admin-staff-card-revoke"),
    path("staff-cards/<int:pk>/print-face", StaffCardPrintFaceView.as_view(), name="admin-staff-card-print-face"),
    path("staff-cards/<int:pk>/download", StaffCardDownloadView.as_view(), name="admin-staff-card-download"),
    path(_DESIGN, CardDesignDetailView.as_view(), name="admin-card-design"),
    path(f"{_DESIGN}/templates", CardTemplateListView.as_view(), name="admin-card-design-templates"),
    path(f"{_DESIGN}/archive", CardDesignArchiveView.as_view(), name="admin-card-design-archive"),
    path(f"{_DESIGN}/unarchive", CardDesignUnarchiveView.as_view(), name="admin-card-design-unarchive"),
    path(f"{_DESIGN}/publish", CardDesignPublishView.as_view(), name="admin-card-design-publish"),
    path(f"{_DESIGN}/submit", CardDesignSubmitView.as_view(), name="admin-card-design-submit"),
    path(f"{_DESIGN}/approve", CardDesignApproveView.as_view(), name="admin-card-design-approve"),
    path(f"{_DESIGN}/reject", CardDesignRejectView.as_view(), name="admin-card-design-reject"),
    path(f"{_DESIGN}/reset", CardDesignResetView.as_view(), name="admin-card-design-reset"),
    path(f"{_DESIGN}/export", CardDesignExportView.as_view(), name="admin-card-design-export"),
    path(f"{_DESIGN}/import", CardDesignImportView.as_view(), name="admin-card-design-import"),
    path(f"{_DESIGN}/preview", CardDesignPreviewView.as_view(), name="admin-card-design-preview"),
    # E-B1: the Events badge designer (badge_v1 documents, role variants, design files).
    path("events/<int:pk>/badge-designs", EventBadgeDesignsView.as_view(), name="admin-event-badge-designs"),
    path("events/<int:pk>/badge-designs/<slug:role>", EventBadgeDesignRoleView.as_view(),
         name="admin-event-badge-design-role"),
    path(f"{_DESIGN}/badge-export", CardDesignBadgeExportView.as_view(), name="admin-card-design-badge-export"),
    path(f"{_DESIGN}/badge-import", CardDesignBadgeImportView.as_view(), name="admin-card-design-badge-import"),
    path(f"{_DESIGN}/convert-to-free-canvas", CardDesignBadgeConvertView.as_view(),
         name="admin-card-design-badge-convert"),
    path(f"{_DESIGN}/revisions", CardDesignRevisionListView.as_view(), name="admin-card-design-revisions"),
    path(f"{_DESIGN}/revisions/<int:revision>", CardDesignRevisionDetailView.as_view(),
         name="admin-card-design-revision"),
    path(f"{_DESIGN}/revisions/<int:revision>/restore", CardDesignRestoreView.as_view(),
         name="admin-card-design-restore"),
    path(f"{_DESIGN}/holders", CardDesignHolderListView.as_view(), name="admin-card-design-holders"),
    path(f"{_DESIGN}/calibration", CardDesignCalibrationView.as_view(), name="admin-card-design-calibration"),
    path(f"{_DESIGN}/assets", CardAssetUploadView.as_view(), name="admin-card-design-assets"),
    path(f"{_DESIGN}/assets/finalize", CardAssetFinalizeView.as_view(), name="admin-card-design-asset-finalize"),
    path(f"{_DESIGN}/assets/<uuid:asset_id>", CardAssetContentView.as_view(), name="admin-card-design-asset"),
    path(f"{_DESIGN}/fonts", CardFontListView.as_view(), name="admin-card-design-fonts"),
    path(f"{_DESIGN}/fonts/prepare", CardFontPrepareView.as_view(), name="admin-card-design-font-prepare"),
    path(f"{_DESIGN}/fonts/<slug:family_slug>/<int:weight>", CardFontFileView.as_view(),
         name="admin-card-design-font-file"),
    path("card-jobs/<int:pk>", CardJobDetailView.as_view(), name="admin-card-job"),
    path("card-jobs/<int:pk>/cancel", CardJobCancelView.as_view(), name="admin-card-job-cancel"),
    path("card-jobs/<int:pk>/result", CardJobResultView.as_view(), name="admin-card-job-result"),
]
