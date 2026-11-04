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

from .views_assets import (CardAssetContentView, CardAssetFinalizeView, CardAssetUploadView, CardFontFileView,
                           CardFontListView, CardFontPrepareView)
from .views_design_actions import (CardDesignApproveView, CardDesignExportView, CardDesignImportView,
                                   CardDesignPreviewView, CardDesignPublishView, CardDesignRejectView,
                                   CardDesignResetView, CardDesignSubmitView)
from .views_designs import CardDesignDetailView, CardTemplateListView, SpaceCardDesignListView
from .views_jobs import CardJobCancelView, CardJobDetailView, CardJobResultView, MemberCardJobListView

_SPACE = "makerspaces/<int:makerspace_id>"
_DESIGN = "card-designs/<int:pk>"

urlpatterns = [
    path(f"{_SPACE}/member-card-settings", MemberCardSettingsView.as_view(), name="admin-member-card-settings"),
    path(f"{_SPACE}/card-designs", SpaceCardDesignListView.as_view(), name="admin-card-designs"),
    path(f"{_SPACE}/member-card-jobs", MemberCardJobListView.as_view(), name="admin-member-card-jobs"),
    path(f"{_SPACE}/member-cards/presence-check-in", MemberCardPresenceView.as_view(),
         name="admin-member-card-presence"),
    path("member-cards/<int:pk>/download", MemberCardDownloadView.as_view(), name="admin-member-card-download"),
    path("member-cards/<int:pk>/email", MemberCardEmailView.as_view(), name="admin-member-card-email"),
    path("member-cards/<int:pk>/photo-request", MemberCardPhotoRequestView.as_view(),
         name="admin-member-card-photo-request"),
    path(_DESIGN, CardDesignDetailView.as_view(), name="admin-card-design"),
    path(f"{_DESIGN}/templates", CardTemplateListView.as_view(), name="admin-card-design-templates"),
    path(f"{_DESIGN}/publish", CardDesignPublishView.as_view(), name="admin-card-design-publish"),
    path(f"{_DESIGN}/submit", CardDesignSubmitView.as_view(), name="admin-card-design-submit"),
    path(f"{_DESIGN}/approve", CardDesignApproveView.as_view(), name="admin-card-design-approve"),
    path(f"{_DESIGN}/reject", CardDesignRejectView.as_view(), name="admin-card-design-reject"),
    path(f"{_DESIGN}/reset", CardDesignResetView.as_view(), name="admin-card-design-reset"),
    path(f"{_DESIGN}/export", CardDesignExportView.as_view(), name="admin-card-design-export"),
    path(f"{_DESIGN}/import", CardDesignImportView.as_view(), name="admin-card-design-import"),
    path(f"{_DESIGN}/preview", CardDesignPreviewView.as_view(), name="admin-card-design-preview"),
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
